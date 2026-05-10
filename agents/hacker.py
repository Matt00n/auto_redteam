from core.llm import LLMProvider

class Hacker:
    """
    Translates a Mastermind hypothesis into executable code (Playwright, Python WS client, or Computer Use).
    """
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        
    def write_exploit_script(self, hypothesis_json_str: str) -> str:
        system_prompt = (
            "You are the Hacker, an elite red-team execution agent.\n"
            "Given an attack hypothesis, write a complete, executable Python script to test it.\n"
            "Output ONLY the Python code, surrounded by ```python ... ```.\n\n"
            "If the execution_mode is 'automated' and requires browser interaction, you MUST use Playwright (sync API).\n"
            "CRITICAL PLAYWRIGHT RULES:\n"
            "1. You MUST read the 'ARTIFACT_DIR' environment variable. Save all screenshots and traces there.\n"
            "2. Wrap your execution in a try/except block to catch failures and ensure the browser closes.\n"
            "3. Use this specific template for Playwright scripts:\n\n"
            "import os\n"
            "import traceback\n"
            "from playwright.sync_api import sync_playwright\n\n"
            "artifact_dir = os.environ.get('ARTIFACT_DIR', './artifacts')\n"
            "target_url = 'http://127.0.0.1:8000/assignments/test-123/' # Adjust as necessary\n\n"
            "def run():\n"
            "    with sync_playwright() as p:\n"
            "        browser = p.chromium.launch(headless=True)\n"
            "        context = browser.new_context()\n"
            "        # Start tracing for reproducible analysis\n"
            "        context.tracing.start(screenshots=True, snapshots=True)\n"
            "        page = context.new_page()\n"
            "        try:\n"
            "            page.goto(target_url)\n"
            "            page.wait_for_load_state('networkidle')\n"
            "            # --- YOUR EXPLOIT LOGIC HERE ---\n"
            "            # e.g., page.evaluate('GlobalState.internalClipboard = ...')\n\n"
            "            # Always take a final screenshot\n"
            "            page.screenshot(path=os.path.join(artifact_dir, 'final_state.png'))\n"
            "        except Exception as e:\n"
            "            print(f'Execution Error: {e}')\n"
            "            traceback.print_exc()\n"
            "            page.screenshot(path=os.path.join(artifact_dir, 'error_state.png'))\n"
            "        finally:\n"
            "            context.tracing.stop(path=os.path.join(artifact_dir, 'trace.zip'))\n"
            "            browser.close()\n\n"
            "if __name__ == '__main__':\n"
            "    run()\n\n"
            "If the hypothesis focuses on WebSockets, write a standard Python script using `websockets` or `websocket-client`."
        )
        
        response = self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Hypothesis:\n{hypothesis_json_str}"}
            ]
        )
        
        content = response.content
        # Extract the python code block
        if "```python" in content:
            code = content.split("```python")[1].split("```")[0].strip()
        elif "```" in content:
            code = content.split("```")[1].split("```")[0].strip()
        else:
            code = content.strip()
            
        return code
