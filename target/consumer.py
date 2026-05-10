import logging
import time


from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import connection, close_old_connections
from asgiref.sync import sync_to_async


from .models import AssignmentTaker
from .aredis_client import aredis_client as redis


logger = logging.getLogger(__name__)


class TextEditorConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        # enforce single connection

        # (1) acquire lock / semaphore
        # the lock does not block; client handles retries
        self.lock = redis.lock('editor:' + str(self.scope['url_route']['kwargs']['assignment_taker_id']),
                               blocking=False)

        if not await self.lock.acquire():
            # (2a) lock not acquired
            # reject connection
            await self.close()
            # send message to same assignment_taker_id consumers to disconnect
            await self.channel_layer.group_send(str(self.scope['url_route']['kwargs']['assignment_taker_id']),
                                                {'type': 'editor.disconnect'})
            return
        
        # (2b) lock acquired
        # accept & upgrade WebSocket connection, close later if not allowed (b/c of timeouts)
        await self.accept()

        # join group to receive disconnects (=> only lock holder receives messages)
        await self.channel_layer.group_add(str(self.scope['url_route']['kwargs']['assignment_taker_id']),
                                           self.channel_name)

        try:
            self.assignment_taker = await AssignmentTaker.objects.aget(
                assignment_taker_id=self.scope['url_route']['kwargs']['assignment_taker_id'])
        except AssignmentTaker.DoesNotExist:
            await self.close(code=4004)
            return

        # Make sure session exists and user is authenticated for this session
        @sync_to_async
        def check_auth(session, taker_id):
            return session.get(f'authenticated_{taker_id}')

        if not self.scope.get('session') or not await check_auth(self.scope['session'], self.assignment_taker.assignment_taker_id):
            await self.close(code=4003)
            return

        # Send initial state to client immediately
        # We still send the last saved text so the UI knows where to start if needed, but no version
        await self.send_json({
            "type": "init",
            "full_text": self.assignment_taker.last_submission_text or ''
        })

        # --- Rate Limiting (Token Bucket) ---
        self._rate_limit_tokens = 60.0
        self._last_refill_time = time.time()
    
    async def editor_disconnect(self, event):
        # leave group: no need for further disconnect messages
        await self.channel_layer.group_discard(str(self.assignment_taker.assignment_taker_id),
                                               self.channel_name)
        await self.close(code=4009)

    async def disconnect(self, close_code):
        # if close() is called during connect(), disconnect() is called
        # this can happen before assignment_taker or lock are initialised or acquired
        if hasattr(self, 'assignment_taker'):
            try:
                # catch any database error to always release the redis lock
                await self.persist_user()
            except:
                logger.exception('%s persist failed', getattr(self.assignment_taker, "assignment_taker_id", "<missing>"))
        if hasattr(self, 'lock') and await self.lock.owned():
            await self.lock.release()

    async def receive_json(self, content):
        # --- Rate Limiting (Token Bucket) ---
        current_time = time.time()
        elapsed = current_time - self._last_refill_time
        self._last_refill_time = current_time
        
        # Refill tokens: 15 per second, cap at 60
        self._rate_limit_tokens = min(60.0, self._rate_limit_tokens + elapsed * 15.0)

        cost = 1
        if self._rate_limit_tokens < cost:
            logger.warning('Rate limit exceeded for %s.', 
                           getattr(self.assignment_taker, "assignment_taker_id", "<missing>"))
            await self.send_json({
                'type': 'error',
                'message': 'You are typing too fast. Please slow down.'
            })
            return
        
        self._rate_limit_tokens -= cost

        action_type = content.get('type')
        text = content.get('text', '')

        # --- Anti-Paste / Validation ---
        if action_type == 'insert' and len(text) > 1 and text != '\\n':
            logger.warning('Paste detected/blocked for %s. Len: %s.', 
                           getattr(self.assignment_taker, "assignment_taker_id", "<missing>"), 
                           len(text))
            await self.send_json({
                'type': 'error',
                'message': 'Pasting is not allowed. Please refresh the page if your editor desynchronized.'
            })
            return

        # --- Apply Action ---
        try:
            # Log to DB (Fire and forget, but confirm safe execution)
            if action_type in ('insert', 'delete', 'paste'):
                start_pos = content.get('from')
                end_pos = content.get('to')
                target_pos = content.get('target')
                log_text = text if action_type == 'insert' else None
                await self.write(action_type, log_text, start_pos, end_pos, target_pos)


        except Exception as e:
            logger.exception('Error processing input for %s', 
                             getattr(self.assignment_taker, "assignment_taker_id", "<missing>"))
            await self.send_json({
                'type': 'error',
                'message': 'Server encountered an error processing your input. Please refresh the page.'
            })

    @sync_to_async(thread_sensitive=False)
    def persist_user(self):
        """
        The persistor stored procedure is called in a new thread (thread_sensitive=False)
        so as not to block database access elsewhere (e.g., middle ware, write()).
        Afterwards, the connection is cleaned up. This is similar to Channel's database_sync_to_async.
        """
    
        with connection.cursor() as cursor:
            cursor.execute('EXEC usp_EditorWritePersistBuffer @assignment_taker_id = %s',
                           (self.assignment_taker.assignment_taker_id,))
        close_old_connections()
    
    @sync_to_async
    def write(self, action, text, start, end, target):
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO editor_write_buffer (posted_date, assignment_taker_id, [action], [text], [start], [end], [target]) VALUES (SYSUTCDATETIME(), %s, %s, %s, %s, %s, %s)",
                [self.assignment_taker.assignment_taker_id, action, text, start, end, target])