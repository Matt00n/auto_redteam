from playwright.sync_api import sync_playwright

class Judge:
    """
    Evaluates the success of an execution run against the local target using purely behavioral (Black-Box) validation.
    """
    def __init__(self, target_url: str = "http://127.0.0.1:8000/assignments/test-123/"):
        self.target_url = target_url
        
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
                page.wait_for_load_state('networkidle')
                
                # Simulate a real user deleting all text to ensure the WS backend gets the delete event
                textarea = page.locator('#textarea1')
                textarea.click()
                page.keyboard.press('Control+A')
                page.keyboard.press('Meta+A') # Fallback for macOS
                page.keyboard.press('Backspace')
                
                # Wait a moment for the WebSocket to sync the deletion to the backend
                page.wait_for_timeout(1000)
                
                # Reload the page to verify the backend actually saved the empty state
                page.reload()
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(2000) # Wait for WebSocket init to populate the field
                
                text = page.locator('#textarea1').input_value()
                if len(text) > 0:
                    raise Exception(f"Editor failed to reset. It still contains {len(text)} characters. Check backend connection.")
                
                print("[Judge] Target state successfully reset and verified empty.")
                
            except Exception as e:
                print(f"[Judge] Error during reset: {e}")
                # Re-raise to alert the main loop that the sandbox is polluted
                raise e
            finally:
                browser.close()
        
    def evaluate_success(self, assignment_taker_id: str, threshold: int = 20) -> dict:
        """
        Opens a fresh browser context, navigates to the page, and checks if arbitrarily long text persisted.
        Returns a dictionary with nuanced success metrics.
        """
        print(f"[Judge] Evaluating state for assignment_taker_id: {assignment_taker_id}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Create a fresh context to ensure no local storage or cache is artificially inflating results
            context = browser.new_context()
            page = context.new_page()
            
            try:
                page.goto(self.target_url)
                page.wait_for_load_state('networkidle')
                
                # Give the WebSocket time to initialize and populate the field from the backend
                page.wait_for_timeout(2000)
                
                text = page.locator('#textarea1').input_value()
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
                    "length": length
                }
                
            except Exception as e:
                err_msg = f"Error during evaluation: {e}"
                print(f"[Judge] {err_msg}")
                return {
                    "success": False,
                    "score": 0.0,
                    "diagnostics": err_msg,
                    "length": 0
                }
            finally:
                browser.close()
