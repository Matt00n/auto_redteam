from core.llm import LLMProvider


class Hacker:
    """
    Translates a Mastermind hypothesis into executable code (Playwright, Python WS client, or Computer Use).
    """

    def __init__(self, llm: LLMProvider, model: str = "gemma-heretic7"):
        self.llm = llm
        self.model = model

    def _extract_code(self, content: str) -> str:
        if "```python" in content:
            return content.split("```python")[1].split("```")[0].strip()
        elif "```" in content:
            return content.split("```")[1].split("```")[0].strip()
        else:
            return content.strip()

    def write_exploit_script(
        self,
        hypothesis_json: str,
        target_url: str = "http://127.0.0.1:8000/assignments/test-123/",
        feedback: str = None,
        browser_choice: str = "chromium",
    ) -> str:
        """
        Translates a hypothesis into executable Python or Playwright code.
        If feedback is provided, acts as a revision step.
        """
        if browser_choice not in ["chromium", "firefox", "webkit"]:
            browser_choice = "chromium"

        import json
        import os

        try:
            hypothesis_dict = json.loads(hypothesis_json)
            execution_mode = hypothesis_dict.get("execution_mode", "automated")
        except Exception:
            execution_mode = "automated"

        system_prompt = (
            "You are the Hacker. Your job is to translate red-team attack hypotheses into executable Python code.\n"
            "Output ONLY the Python code, surrounded by ```python ... ```.\n"
        )

        if execution_mode == "direct_websocket":
            system_prompt += (
                "You MUST output a script that connects directly to the Django Channels WebSocket endpoint using the `websockets` library.\n"
                "You will use a quick headless Playwright context to obtain the session cookies and assignment details, then communicate directly via the WebSocket.\n"
                "YOU MUST STRICTLY USE THIS EXACT TEMPLATE (fill in the logic between the lines):\n"
                "```python\n"
                "import os\n"
                "import json\n"
                "import asyncio\n"
                "import traceback\n"
                "from playwright.sync_api import sync_playwright\n"
                "import websockets\n\n"
                "def get_session_info():\n"
                "    with sync_playwright() as p:\n"
                f"        browser = p.{browser_choice}.launch(headless=True)\n"
                "        context = browser.new_context()\n"
                "        page = context.new_page()\n"
                "        try:\n"
                f"            page.goto('{target_url}')\n"
                "            page.wait_for_load_state('networkidle')\n"
                "            if page.locator('#password').count() > 0:\n"
                "                page.fill('#password', '81EXnwS2Wqa6Snrv')\n"
                "                page.click('.submit-btn')\n"
                "                page.wait_for_selector('#textarea1', timeout=10000)\n"
                "                page.reload()\n"
                "                page.wait_for_load_state('networkidle')\n"
                "            page.wait_for_selector('#textarea1', timeout=10000)\n"
                "            page.wait_for_function('() => { const el = document.getElementById(\"textarea1\"); return el && !el.disabled; }', timeout=15000)\n"
                "            taker_id = page.evaluate('window.GlobalState ? window.GlobalState.assignmentTakerId : null')\n"
                "            cookies = context.cookies()\n"
                "            cookie_str = '; '.join([f\"{c['name']}={c['value']}\" for c in cookies])\n"
                "            host = page.evaluate('window.location.host')\n"
                "            protocol = 'wss' if page.evaluate('window.location.protocol') == 'https:' else 'ws'\n"
                "            ws_url = f'{protocol}://{host}/ws/assignments/{taker_id}/'\n"
                "            return ws_url, cookie_str\n"
                "        finally:\n"
                "            browser.close()\n\n"
                "async def run_exploit(ws_url, cookie_str):\n"
                "    headers = {'Cookie': cookie_str}\n"
                "    artifact_dir = os.environ.get('ARTIFACT_DIR', 'sandbox')\n"
                "    try:\n"
                "        async with websockets.connect(ws_url, extra_headers=headers) as ws:\n"
                "            # Wait for initial state\n"
                "            init_msg = await ws.recv()\n"
                "            print(f'Connected. Init message: {init_msg}')\n"
                "            # --- YOUR DIRECT WEBSOCKET EXPLOIT LOGIC HERE ---\n"
                "            # E.g. Send single character inserts sequentially with delay to match rate-limit\n"
                "            # E.g. await ws.send(json.dumps({'type': 'insert', 'text': 'a', 'from': 0, 'to': 0}))\n"
                "            # E.g. await asyncio.sleep(0.07)\n"
                "    except websockets.exceptions.ConnectionClosed as cc:\n"
                "        print(f'WEBSOCKET_ERROR: Connection closed abnormally. Code={cc.code}, Reason={cc.reason}')\n"
                "        raise\n"
                "    except Exception as e:\n"
                "        print(f'WEBSOCKET_ERROR: Failed connection or communication: {e}')\n"
                "        raise\n\n"
                "def run():\n"
                "    try:\n"
                "        ws_url, cookie_str = get_session_info()\n"
                "        print(f'Obtained WS URL: {ws_url}')\n"
                "        asyncio.run(run_exploit(ws_url, cookie_str))\n"
                "    except Exception as e:\n"
                "        print(f'Execution Error: {e}')\n"
                "        traceback.print_exc()\n\n"
                "if __name__ == '__main__':\n"
                "        run()\n"
                "```\n"
            )
        elif execution_mode == "automated":
            system_prompt += (
                "You MUST output a fully working Playwright script targeting the requested browser.\n"
                "YOU MUST STRICTLY USE THIS EXACT TEMPLATE (fill in the logic between the lines):\n"
                "```python\n"
                "import os\n"
                "import traceback\n"
                "from playwright.sync_api import sync_playwright\n\n"
                "def robust_locator(page, selectors):\n"
                '    """Tries multiple selector fallbacks to find and return a visible locator."""\n'
                "    for s in selectors:\n"
                "        loc = page.locator(s)\n"
                "        try:\n"
                "            if loc.count() > 0:\n"
                "                return loc\n"
                "        except:\n"
                "            continue\n"
                "    # Fallback to first selector if none matched\n"
                "    return page.locator(selectors[0])\n\n"
                "def run():\n"
                "    with sync_playwright() as p:\n"
                f"        browser = p.{browser_choice}.launch(headless=True)\n"
                "        context = browser.new_context()\n"
                "        page = context.new_page()\n"
                "        artifact_dir = os.environ.get('ARTIFACT_DIR', 'sandbox')\n"
                "        log_file_path = os.path.join(artifact_dir, 'browser_logs.txt')\n"
                "        def log_msg(msg):\n"
                "            with open(log_file_path, 'a') as f: f.write(f'CONSOLE: {{msg.text}}\\n')\n"
                "        def log_err(err):\n"
                "            with open(log_file_path, 'a') as f: f.write(f'ERROR: {{err}}\\n')\n"
                "        page.on('console', log_msg)\n"
                "        page.on('pageerror', log_err)\n"
                "        context.tracing.start(screenshots=True, snapshots=True)\n"
                "        try:\n"
                f"            page.goto('{target_url}')\n"
                "            page.wait_for_load_state('networkidle')\n"
                "            if page.locator('#password').count() > 0:\n"
                "                page.fill('#password', '81EXnwS2Wqa6Snrv')\n"
                "                page.click('.submit-btn')\n"
                "                page.wait_for_selector('#textarea1', timeout=10000)\n"
                "                page.reload()\n"
                "                page.wait_for_load_state('networkidle')\n"
                "            page.wait_for_selector('#textarea1', timeout=10000)\n"
                "            page.wait_for_function('() => { const el = document.getElementById(\"textarea1\"); return el && !el.disabled; }', timeout=15000)\n"
                "            # --- YOUR EXPLOIT LOGIC HERE ---\n"
                "            # E.g. To type in editor, locate robustly: \n"
                "            # el = robust_locator(page, ['#textarea1', 'textarea', '[contenteditable=\"true\"]'])\n"
                "            # el.click()\n"
                "            page.screenshot(path=os.path.join(artifact_dir, 'final_state.png'))\n"
                "        except Exception as e:\n"
                "            print(f'Execution Error: {{e}}')\n"
                "            traceback.print_exc()\n"
                "            page.screenshot(path=os.path.join(artifact_dir, 'error_state.png'))\n"
                "        finally:\n"
                "            context.tracing.stop(path=os.path.join(artifact_dir, 'trace.zip'))\n"
                "            browser.close()\n\n"
                "if __name__ == '__main__':\n"
                "    run()\n"
                "```\n"
            )
        elif execution_mode == "human_involved":
            system_prompt += (
                "DO NOT write Playwright code. Instead, generate a highly structured Markdown 'Test Card' printed to stdout using `print()` with the following sections:\n"
                "  - What the tester should do (step-by-step)\n"
                "  - What to observe\n"
                "  - What counts as success\n"
                "  - What state to record before and after\n"
                "  - How to avoid contaminating the result (e.g. clear clipboard, disable extensions)\n\n"
            )
        elif execution_mode == "computer_use":
            docs_path = os.path.join(
                os.path.dirname(__file__), "..", "prompts", "computer_use_api.md"
            )
            docs_content = ""
            if os.path.exists(docs_path):
                with open(docs_path, "r") as f:
                    docs_content = f.read()
            system_prompt += (
                "You MUST write a Python script that utilizes OS-level automation libraries like `pyautogui` or `pynput`, or interact with a Computer Use LLM API to control the mouse and keyboard directly.\n\n"
                f"API REFERENCE / EXAMPLES:\n{docs_content}\n"
            )

        user_prompt = f"Target Hypothesis:\n{hypothesis_json}\n\n"
        if feedback:
            user_prompt += f"CRITIC FEEDBACK (YOUR PREVIOUS SCRIPT WAS REJECTED):\n{feedback}\n\nPlease provide a corrected script.\n"
        else:
            user_prompt += "Write the complete, self-contained Python script to execute this attack."

        response = self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model,
        )

        return self._extract_code(response.content)
