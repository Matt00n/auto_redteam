from core.llm import LLMProvider

class Hacker:
    """
    Translates a Mastermind hypothesis into executable code (Playwright, Python WS client, or Computer Use).
    """
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        
    def _get_playwright_template(self) -> str:
        return (
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
            "        page = context.new_page()\n"
            "        # Capture browser logs for partial signals\n"
            "        log_file_path = os.path.join(artifact_dir, 'browser_logs.txt')\n"
            "        def log_msg(msg):\n"
            "            with open(log_file_path, 'a') as f: f.write(f'CONSOLE: {msg.text}\\n')\n"
            "        def log_err(err):\n"
            "            with open(log_file_path, 'a') as f: f.write(f'ERROR: {err}\\n')\n"
            "        page.on('console', log_msg)\n"
            "        page.on('pageerror', log_err)\n"
            "        # Start tracing for reproducible analysis\n"
            "        context.tracing.start(screenshots=True, snapshots=True)\n"
            "        try:\n"
            "            page.goto(target_url)\n"
            "            page.wait_for_load_state('networkidle')\n"
            "            # --- YOUR EXPLOIT LOGIC HERE ---\n"
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
            "If the hypothesis focuses on WebSockets, write a standard Python script using `websockets` or `websocket-client`.\n"
        )

    def _extract_code(self, content: str) -> str:
        if "```python" in content:
            return content.split("```python")[1].split("```")[0].strip()
        elif "```" in content:
            return content.split("```")[1].split("```")[0].strip()
        else:
            return content.strip()
        
    def write_exploit_script(self, hypothesis: str, feedback: str = None) -> str:
        """
        Translates a hypothesis into executable Python or Playwright code.
        If feedback is provided, acts as a revision step.
        """
        system_prompt = (
            "You are the Hacker. Your job is to translate red-team attack hypotheses into executable Python code.\n"
            "Output ONLY the Python code, surrounded by ```python ... ```.\n"
            "If the attack targets the frontend, USE PLAYWRIGHT and strictly follow the Playwright template. "
            "If the attack targets WebSockets or backend logic, use standard Python (`websockets`, `requests`). "
            "IMPORTANT: If the execution mode is 'human_involved', print out instructions to stdout instead. "
            "\n\n"
        )
        system_prompt += self._get_playwright_template()
        
        user_prompt = f"Target Hypothesis:\n{hypothesis}\n\n"
        if feedback:
            user_prompt += f"CRITIC FEEDBACK (YOUR PREVIOUS SCRIPT WAS REJECTED):\n{feedback}\n\nPlease provide a corrected script.\n"
        else:
            user_prompt += "Write the complete, self-contained Python script to execute this attack."

        response = self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="gpt-4o"
        )
        
        return self._extract_code(response.content)
