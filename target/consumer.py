import asyncio
import logging
import time

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import close_old_connections, connection

from .aredis_client import aredis_client as redis
from .models import AssignmentTaker

logger = logging.getLogger(__name__)


class TextEditorConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # enforce single connection
        assignment_taker_id = str(
            self.scope["url_route"]["kwargs"]["assignment_taker_id"]
        )
        self._is_disconnecting = False  # Guard flag to prevent lifecycle races

        # 1. Verify Session / Authentication
        @sync_to_async
        def check_auth(session, taker_id):
            return session.get(f"authenticated_{taker_id}") if session else False

        if not await check_auth(
            self.scope.get("session"), self.assignment_taker.assignment_taker_id
        ):
            await self.close(code=4003)
            return

        # 2. ONLY NOW acquire the lock (Newest Connection Wins approach)
        self.lock = redis.lock(
            "editor:" + assignment_taker_id, timeout=60, blocking=False
        )

        if not await self.lock.acquire():
            # Evict the older connection
            await self.channel_layer.group_send(
                assignment_taker_id, {"type": "editor.disconnect"}
            )
            # Give the old connection up to 1 second to release the lock
            for _ in range(25):
                await asyncio.sleep(0.2)
                if await self.lock.acquire():
                    break
            else:
                logger.warning(
                    "[WS] Lock acquisition timed out for ID: %s", assignment_taker_id
                )
                await self.close(code=4009)
                return

        # 3. Load the assignment taker object from DB first
        try:
            self.assignment_taker = await AssignmentTaker.objects.aget(
                assignment_taker_id=assignment_taker_id
            )
        except AssignmentTaker.DoesNotExist:
            await self.close(code=4004)
            return

        # --- Rate Limiting (Token Bucket) ---
        self._rate_limit_tokens = 60.0
        self._last_refill_time = time.time()

        # 4. Accept the connection and join the group
        await self.accept()
        await self.channel_layer.group_add(assignment_taker_id, self.channel_name)

        # Start a background task to keep the lock alive
        self.heartbeat_task = asyncio.create_task(self._lock_heartbeat())

        # 5. Send initial state
        await self.send_json(
            {
                "type": "init",
                "full_text": self.assignment_taker.last_submission_text or "",
            }
        )

    async def editor_disconnect(self, event):
        if self._is_disconnecting:
            return
        # leave group: no need for further disconnect messages
        await self.channel_layer.group_discard(
            str(self.assignment_taker.assignment_taker_id), self.channel_name
        )
        await self.close(code=4009)

    async def disconnect(self, close_code):
        # Prevent concurrent executions of disconnect pipelines
        if self._is_disconnecting:
            return
        self._is_disconnecting = True

        # 1. Cancel the heartbeat task so it doesn't leak memory
        if hasattr(self, "heartbeat_task"):
            self.heartbeat_task.cancel()

        # 2. Defensively release the Redis lock
        if hasattr(self, "lock"):
            try:
                # Check ownership first to prevent throwing unnecessary LockErrors
                if await self.lock.owned():
                    await self.lock.release()
            except Exception as e:
                # Check if it's a lock ownership error to avoid traceback spam during 403s
                if "not owned" in str(e) or "already unlocked" in str(e):
                    logger.info(
                        "Redis lock already released or unowned for %s (Expected during 403/handshake failure)",
                        getattr(
                            getattr(self, "assignment_taker", None),
                            "assignment_taker_id",
                            "<missing>",
                        ),
                    )
                else:
                    # Real infrastructure or connection errors still get full tracebacks
                    logger.exception(
                        "Unexpected failure releasing lock for %s",
                        getattr(
                            getattr(self, "assignment_taker", None),
                            "assignment_taker_id",
                            "<missing>",
                        ),
                    )

        # 3. Save user state to the database if initialized
        if hasattr(self, "assignment_taker"):
            try:
                await self.persist_user()
            except Exception:
                logger.exception(
                    "%s persist failed",
                    getattr(self.assignment_taker, "assignment_taker_id", "<missing>"),
                )

    async def _lock_heartbeat(self):
        """Periodically refreshes the Redis lock while connected."""
        try:
            while True:
                # Sleep for 20 seconds (well within the 60-second TTL)
                await asyncio.sleep(20)
                if hasattr(self, "lock") and await self.lock.owned():
                    await self.lock.reacquire()
        except asyncio.CancelledError:
            # Task was cancelled normally on disconnect
            pass
        except Exception as e:
            logger.exception("Heartbeat error")

    async def receive_json(self, content):
        # --- Rate Limiting (Token Bucket) ---
        current_time = time.time()
        elapsed = current_time - self._last_refill_time
        self._last_refill_time = current_time

        # Refill tokens: 15 per second, cap at 60
        self._rate_limit_tokens = min(60.0, self._rate_limit_tokens + elapsed * 15.0)

        cost = 1
        if self._rate_limit_tokens < cost:
            logger.warning(
                "Rate limit exceeded for %s.",
                getattr(self.assignment_taker, "assignment_taker_id", "<missing>"),
            )
            await self.send_json(
                {
                    "type": "error",
                    "message": "You are typing too fast. Please slow down.",
                }
            )
            return

        self._rate_limit_tokens -= cost

        action_type = content.get("type")
        text = content.get("text", "")

        # --- Anti-Paste / Validation ---
        if action_type == "insert" and len(text) > 1 and text != "\\n":
            logger.warning(
                "Paste detected/blocked for %s. Len: %s.",
                getattr(self.assignment_taker, "assignment_taker_id", "<missing>"),
                len(text),
            )
            await self.send_json(
                {
                    "type": "error",
                    "message": "Pasting is not allowed. Please refresh the page if your editor desynchronized.",
                }
            )
            return

        # --- Apply Action ---
        try:
            # Log to DB (Fire and forget, but confirm safe execution)
            if action_type in ("insert", "delete", "paste"):
                start_pos = content.get("from")
                end_pos = content.get("to")
                target_pos = content.get("target")
                log_text = text if action_type == "insert" else None
                await self.write(action_type, log_text, start_pos, end_pos, target_pos)

        except Exception as e:
            logger.exception(
                "Error processing input for %s",
                getattr(self.assignment_taker, "assignment_taker_id", "<missing>"),
            )
            await self.send_json(
                {
                    "type": "error",
                    "message": "Server encountered an error processing your input. Please refresh the page.",
                }
            )

    @sync_to_async(thread_sensitive=False)
    def persist_user(self):
        """
        The persistor stored procedure is called in a new thread (thread_sensitive=False)
        so as not to block database access elsewhere (e.g., middle ware, write()).
        Afterwards, the connection is cleaned up. This is similar to Channel's database_sync_to_async.
        """

        with connection.cursor() as cursor:
            cursor.execute(
                "EXEC usp_EditorWritePersistBuffer @assignment_taker_id = %s",
                (self.assignment_taker.assignment_taker_id,),
            )
        close_old_connections()

    @sync_to_async(thread_sensitive=False)
    def write(self, action, text, start, end, target):
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO editor_write_buffer (posted_date, assignment_taker_id, [action], [text], [start], [end], [target]) VALUES (SYSUTCDATETIME(), %s, %s, %s, %s, %s, %s)",
                [
                    self.assignment_taker.assignment_taker_id,
                    action,
                    text,
                    start,
                    end,
                    target,
                ],
            )
