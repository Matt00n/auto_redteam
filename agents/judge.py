from playwright.sync_api import sync_playwright


class Judge:
    """
    Evaluates the success of an execution run against the local target using purely behavioral (Black-Box) validation.
    """

    TARGET_PASSWORD = "81EXnwS2Wqa6Snrv"

    def __init__(self, target_url: str = "http://127.0.0.1:8000/assignments/test-123/"):
        self.target_url = target_url

    @staticmethod
    def _ensure_authenticated(page):
        """
        Checks if the page is showing the login form and submits the password if so.
        After a successful AJAX login the DOM swaps to the editor, but the WebSocket
        may be stuck in an exponential-backoff retry loop (initial connection failed
        with 403 before the session cookie existed).  A page.reload() gives a clean
        slate: the WS connects on the first attempt with zero delay.

        After reload we wait for the WebSocket 'init' message to populate the editor
        by watching for the #textarea1 element to become enabled (editor is locked
        while connecting and unlocked in socket.onopen).
        """
        if page.locator("#password").count() > 0:
            page.fill("#password", Judge.TARGET_PASSWORD)
            page.click(".submit-btn")
            # Wait for AJAX login to succeed – the editor textarea appears in the DOM
            page.wait_for_selector("#textarea1", timeout=10000)
            # Allow database session writes to commit and cookies to settle
            page.wait_for_timeout(500)
            # Reload so the WebSocket connects immediately (no backoff from prior 403s)
            page.reload()
            # page.wait_for_function("""
            # () => {
            #     const status = document.getElementById('connectionStatus');
            #     return status && status.innerText.includes('Connected');
            # }
            # """, timeout=15000)
            page.wait_for_load_state("networkidle")

        # Wait for the editor textarea to exist (covers both fresh-load and post-login-reload)
        page.wait_for_selector("#textarea1", timeout=10000)
        # Wait for the WebSocket 'init' message to populate the field and unlock the editor.
        # The frontend sets textarea.disabled = false in socket.onopen, so we wait for that.
        try:
            page.wait_for_function(
                "() => { const el = document.getElementById('textarea1'); return el && !el.disabled; }",
                timeout=15000,
            )
            # Short grace period for initial state payload to be evaluated by onmessage
            page.wait_for_timeout(500)
        except Exception as e:
            # Diagnostic capture: what is the connection status bar currently showing?
            status_text = ""
            if page.locator("#connectionStatus").count() > 0:
                status_text = page.locator("#connectionStatus").inner_text()
            raise Exception(
                f"Editor lock verification failed. UI element state remained disabled. "
                f"Current Frontend Status Banner: '{status_text}'. Internal Error: {e}"
            )

    def reset_target_state(self, assignment_taker_id: str):
        """
        Clears the editor text box by simulating a user pressing Ctrl+A and Backspace.
        Ensures a clean slate before execution.
        """
        print(f"[Judge] Resetting state for assignment_taker_id: {assignment_taker_id}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
                page.goto(self.target_url)
                page.wait_for_load_state("networkidle")
                self._ensure_authenticated(page)

                # Simulate a real user deleting all text to ensure the WS backend gets the delete event
                textarea = page.locator("#textarea1")
                textarea.click()
                # page.keyboard.press("Control+A")
                # page.keyboard.press("Backspace")
                # print(page.locator("#textarea1").input_value())
                # page.keyboard.press("Meta+A")  # Fallback for macOS
                # page.keyboard.press("Backspace")
                # 2. Fetch the current text to determine its length
                text_value = textarea.input_value()
                text_length = len(text_value)
                page.keyboard.press("End")

                # 4. Loop and press Backspace for each character
                for _ in range(text_length):
                    page.keyboard.press("Backspace")

                # Wait for the WebSocket to sync the deletion to the backend
                page.wait_for_timeout(2000)

                # Reload the page to verify the backend actually saved the empty state
                print(page.locator("#textarea1").input_value())
                page.reload()
                page.wait_for_load_state("networkidle")
                self._ensure_authenticated(page)
                print(page.locator("#textarea1").input_value())
                text = page.locator("#textarea1").input_value()
                if len(text) > 0:
                    raise Exception(
                        f"Editor failed to reset. It still contains {len(text)} characters. "
                        "Check backend connection."
                    )

                print("[Judge] Target state successfully reset and verified empty.")

            except Exception as e:
                print(f"[Judge] Error during reset: {e}")
                # Re-raise to alert the main loop that the sandbox is polluted
                raise e
            finally:
                browser.close()

    def evaluate_success(self, assignment_taker_id: str, threshold: int = 200) -> dict:
        """
        Opens a fresh browser context, navigates to the page, and checks if arbitrarily long text persisted.
        Returns a dictionary with nuanced success metrics.
        """
        print(
            f"[Judge] Evaluating state for assignment_taker_id: {assignment_taker_id}"
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Create a fresh context to ensure no local storage or cache is artificially inflating results
            context = browser.new_context()
            page = context.new_page()

            try:
                page.goto(self.target_url)
                page.wait_for_load_state("networkidle")
                self._ensure_authenticated(page)

                text = page.locator("#textarea1").input_value()
                length = len(text)
                print(f"[Judge] Found {length} characters persisted in the database.")

                success = length > threshold
                score = min(10.0, (length / threshold) * 10.0) if not success else 10.0

                if success:
                    notes = f"Success! {length} characters persisted in the database."
                elif length > 0:
                    notes = f"Partial Success: {length} characters persisted, but did not meet threshold ({threshold})."
                else:
                    notes = "Failure: 0 characters persisted in the database."

                return {
                    "success": success,
                    "score": round(score, 1),
                    "diagnostics": notes,
                    "length": length,
                }

            except Exception as e:
                err_msg = f"Error during evaluation: {e}"
                print(f"[Judge] {err_msg}")
                return {
                    "success": False,
                    "score": 0.0,
                    "diagnostics": err_msg,
                    "length": 0,
                }
            finally:
                browser.close()
