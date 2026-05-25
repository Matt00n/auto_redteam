# Computer Use API Cheat Sheet

When operating in `computer_use` mode, your goal is to generate a Python script that leverages OS-level UI automation or an LLM Computer Use API to bypass restrictions visually.

### Option 1: Using OS Automation (`pyautogui`)
If the goal is to perform pure OS automation locally (e.g. typing at an exact speed, or injecting a raw payload via keyboard):
```python
import pyautogui
import time
import os

def run():
    artifact_dir = os.environ.get('ARTIFACT_DIR', 'sandbox')
    print("Waiting 2 seconds for window focus...")
    time.sleep(2)
    
    # Type text very fast, bypassing browser paste events
    pyautogui.write("PAYLOAD", interval=0.01)
    
    # Take screenshot of the result
    screenshot_path = os.path.join(artifact_dir, 'final_state.png')
    pyautogui.screenshot(screenshot_path)
    print(f"Screenshot saved to {screenshot_path}")

if __name__ == '__main__':
    run()
```

### Option 2: Using OpenAI's Visual Computer Tool
If the task requires visual reasoning (e.g., "Find the submit button and click it"), you can write a script that uses the OpenAI API's `computer` tool to execute actions visually on the user's screen. 
*Note: In our framework, your script should execute a single turn or a very short, hardcoded loop, taking a screenshot and passing it to the API.*

```python
import os
import base64
import pyautogui
from openai import OpenAI

def run():
    client = OpenAI()
    artifact_dir = os.environ.get('ARTIFACT_DIR', 'sandbox')
    screenshot_path = os.path.join(artifact_dir, 'current_screen.png')
    
    # Capture the screen
    pyautogui.screenshot(screenshot_path)
    
    with open(screenshot_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
    print("Sending visual context to OpenAI Computer Use tool...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user", 
                "content": [
                    {"type": "text", "text": "Locate the text editor on the screen, click it, and type PAYLOAD."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]
            }
        ],
        tools=[{"type": "computer"}]
    )
    
    # Print the tool calls requested by the visual model
    # (In a full harness, you would execute the returned actions array here)
    print("Requested Actions:", response.choices[0].message.tool_calls)

if __name__ == '__main__':
    run()
```
