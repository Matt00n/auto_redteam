# Auto-RedTeam: Detailed Implementation Plan

This document merges initial brainstorming with constraints around LLM choice, new attack vectors (Computer Use API), specifics from the target application (`assignments.html`, `home.js`, `consumer.py`), and advanced red-team research methodologies (LangGraph/AutoGen structures, Tree of Thoughts, systematic memory logging).

## 1. Core Technology Stack
*   **Primary LLMs:** OpenAI (GPT-5.4 / GPT-5.5) using the official OpenAI API.
*   **Secondary/Fallback LLMs:** Gemini API (ensuring the framework abstracts the LLM provider for easy switching).
*   **Execution Environments:** 
    *   Python (for WebSocket/Network scripts, `pyautogui`/`pynput` for OS-level HID).
    *   Playwright / Puppeteer (for DOM/JS exploits).
    *   OpenAI Computer Use API (`tools-computer-use`) for headless browser automation mirroring human OS-level interaction.

## 2. System Architecture (Multi-Agent Workflow)

The framework operates as a closed-loop search-and-learning system inspired by Co-Scientist, AI-Scientist, and advanced LangGraph workflows.

1.  **The Mastermind (Architect / Planner / Hypothesis Generator):**
    *   *Context Variation:* We instantiate multiple Mastermind personas:
        *   **Black-box Agent:** Sees no code. Must rely on behavioral observations and OS-level attacks (e.g., Computer Use, Virtual HID).
        *   **Grey-box Agent:** Sees only `assignments.html` and `home.js`. Focuses on DOM, JS event overriding, and LocalStorage.
        *   **White-box Agent:** Sees full stack including `consumer.py`. Focuses on bypassing WebSocket rate limits and API logic flaws.
    *   *Role:* Proposes new hypotheses and test families (Tree of Thoughts) rather than just random guesses.
2.  **The Code-Reading Analyst:**
    *   *Role:* Instead of cramming 10,000 lines of code into a prompt, this agent uses RAG (Retrieval-Augmented Generation) to extract a "mechanism map" (e.g., "where is paste blocked?", "which event handlers are relevant?").
3.  **The Reviewer (Critic / Skeptic):**
    *   *Role:* Scrutinizes Mastermind ideas. Asks: "Does it really bypass the defense, or just look like it?", "Is this a duplicate?", "Is there an easier explanation for this success?"
4.  **The Hacker (Executor):**
    *   *Role:* Generates Python scripts, Playwright test files, or sequences of `tools-computer-use` actions. Runs tests with strict discipline (collecting traces, screenshots, exact versions).
5.  **The Judge (Observer / Instrumenter):**
    *   *Role:* Parses the execution output against success metrics (text length > threshold, execution time < max_time, text persists after a hard reload). Collects DOM mutations, network requests, and latency.
6.  **The Historian (Memory Curator / Archivist):**
    *   *Role:* Organizes attempts by *mechanism* rather than surface wording. Manages the Vector DB of past attempts.
7.  **The Human-Interaction Broker:**
    *   *Role:* For attacks requiring a human (HITL), it generates clear instruction cards (SOPs) and parses the human's manual report, keeping the system useful even when execution is partially manual.

## 3. Systematic Memory & Experiment Logging

If the memory is a flat list of prompts, the system will repeat itself. The **Historian** must log the "Vector DNA" in a structured JSON schema:

*   **Attack Family:** (e.g., *UI event-path mismatch, Input modality asymmetry, Timing race, Component boundary confusion*)
*   **Mechanism Hypothesis:** (e.g., "The defense listens for `Ctrl+V` keydown events, but not synthetic `keydown` loops.")
*   **Assumptions & Context:** (Frontend/Backend versions)
*   **Execution Method:** (`automated`, `human_involved`, `browser-driver`)
*   **Outcome & Evidence:** (Success, Partial Success, Defense Triggered, + screenshots/logs)
*   **Scoring Metrics:**
    *   *Success:* Did text enter?
    *   *Novelty:* Is this meaningfully different from prior attempts?
    *   *Reproducibility:* Can it be repeated?
    *   *Generality:* Does it suggest a broader class of weaknesses?
    *   *Diagnostic Value:* Did a failed attempt reveal an important code path?

## 4. Analysis of the Target Defenses

*   **Frontend (`home.js`):**
    *   Blocks native `paste` and `cut` events.
    *   Suppresses drag & drop events.
    *   Blocks spellcheck / auto-fix in `beforeinput`.
    *   Suppresses native Undo/Redo (Ctrl+Z/Y).
    *   Checks length of `insertText` in `beforeinput` (blocks strings `length > 3`).
*   **Backend (`consumer.py`):**
    *   Token Bucket Rate Limiter: Max 60 tokens, refills 15/sec. Cost is 1 per WebSocket message.
    *   Anti-Paste Validation: explicitly checks `if action_type == 'insert' and len(text) > 1 and text != '\\n'`.

## 5. Specific Attack Vectors (Exploration Space)

The system should explore these distinct families of ideas:

### A. Computer Use, OS & Hardware Level (Black-box / Physical)
*   **The "Maximum Legal Speed" Typist:** Utilizing the `tools-computer-use` API or Playwright to simulate keypresses at exactly 14 chars/sec (just under the backend's 15/sec refill rate).
*   **The Burst Typist:** Typing 60 characters instantly (exhausting the bucket), waiting 4 seconds, and repeating.
*   **Virtual HID (Human Interface Device):** Using Python's `pyautogui` or `pynput` to control the mouse and keyboard at the OS level, bypassing the browser entirely.
*   **OCR-to-Keyboard:** Displaying text on screen, using OCR to "read" it, and piping it into a keyboard emulator.

### B. Frontend / DOM Exploits (Grey-box)
*   **Internal Clipboard Hijacking:** `home.js` implements a custom clipboard via `GlobalState.internalClipboard`. Injecting `GlobalState.internalClipboard = {text: "PAYLOAD", ...}; pasteAtCursor();` bypasses the UI constraints.
*   **Event Listener Hijacking:** Executing `element.onpaste = null` or using Chrome DevTools Protocol (CDP) to strip the specific listeners before pasting.
*   **Synthetic Input Emulation:** A JS script iterating through a string, firing `keydown`, `keypress`, and `keyup` for every character to simulate typing, evading `insertText` length checks.
*   **Shadow DOM / Framework Injection:** Checking for Shadow DOM encapsulation limits or directly modifying internal states (e.g., `__reactFiber` equivalents if applicable).
*   **Offline Queue Stuffing:** Disconnecting the network, writing directly to `GlobalState.offlineQueue` or `localStorage.setItem('editor_content_{id}', 'PAYLOAD')`, and reconnecting.

### C. Backend / WebSocket Exploits (White-box)
*   **Action Type Spoofing (Vulnerability in `consumer.py`):** The backend validation ignores length if the `action_type` is not `insert`. A direct WebSocket client sending a `paste` action bypasses the length check.
*   **Concurrent Connections / Lock Drops:** Rapidly connecting/disconnecting to attempt a race condition against the Redis `lock` in `consumer.py`.

### D. Human-in-the-Loop (HITL)
*   **Drag-and-Drop Bypass:** Instructing the human to drag a `.txt` file into the editor (testing if `onDrop` handlers were completely neutralized).
*   **Browser DevTools Override:** Instructing the human to use Chrome's "Local Overrides" to permanently delete the defense scripts from `home.js` on load.

## 6. Implementation Roadmap

### Phase 1: Environment & Sandbox Setup
*   Deploy the local instance of the target Django/Channels app with strict state reset between runs.
*   Setup the agent loop scaffold in Python (LangChain, AutoGen, or pure OpenAI SDK) --> lets use the pure SDK (but abstract it such that we can easily swap in the other LLMs (Gemini) later).
*   Create the "Judge" script that can reliably reset the target's database/state between runs to avoid polluted results.

### Phase 2: Agent Tooling & Memory
*   Implement the structured Vector DB ("Vector DNA" schema) for the Historian.
*   Implement `ComputerUseTool` wrapping OpenAI's new API, `PlaywrightTool` for JS/DOM context, and `PythonExecutionTool` for OS-level and WS scripting.
*   Implement the Code-Reading RAG tool.

### Phase 3: The Evolutionary Learning Loop
*   Implement Bandit-style prioritization and Tree of Thoughts for the Mastermind to pick attack families.
*   Wire the agents (Mastermind -> Code Reader -> Reviewer -> Hacker -> Judge -> Historian).
*   Run the loop autonomously, requesting HITL fallback only when automated methods exhaust or suggest manual edge cases.

### Phase 4: Analysis
*   Review the final categorized report (grouping attempts by mechanism) to identify which bypasses were most effective across the different context personas (Black/Grey/White).
