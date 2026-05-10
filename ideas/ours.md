# Auto-RedTeam: Multi-Agent System for Bypassing Web Defenses

This document outlines ideas for building a multi-agent, LLM-based system designed to autonomously discover, execute, and learn from attack vectors against web-based defenses (specifically bypassing a "no-paste" restriction in a text editor).

Inspired by projects like [AI-Scientist](https://github.com/sakanaai/ai-scientist), [autoresearch](https://github.com/karpathy/autoresearch), and the [Co-Scientist framework (arXiv:2502.18864)](https://arxiv.org/abs/2502.18864), the system operates on an iterative loop of hypothesis generation, experimentation, evaluation, and knowledge accumulation.

## 1. System Architecture (The Multi-Agent Workflow)

To achieve both autonomy and deep exploration, the system should be composed of specialized agents interacting in a cyclical workflow:

*   **The Mastermind (Idea Generation Agent):** Proposes new attack vectors. It is seeded with the system context (frontend code, backend code, or none for black-box testing) and the history of past attempts.
*   **The Reviewer (Critic Agent):** Evaluates the Mastermind's proposals before execution. It filters out redundant ideas, identifies obvious flaws, and scores ideas on "novelty" to ensure the system doesn't get stuck in local minima.
*   **The Hacker (Execution/Coding Agent):** Translates the accepted idea into executable code (e.g., Playwright/Puppeteer scripts, Python network requests, Chrome DevTools Protocol commands) or clear step-by-step SOPs for human execution.
*   **The Judge (Evaluation Agent):** Runs the execution code against the local website instance. It measures success based on the core criteria:
    *   Was arbitrarily long text inserted?
    *   Was it done within a reasonable time frame?
    *   Did it persist upon page reload?
    *   *Mechanism:* The Judge clears the database/text box before each attempt to ensure a clean slate, then performs the validation steps.
*   **The Archivist (Memory & Logging System):** Logs all attempts systematically (idea, code, logs, success/failure status, time taken) into a structured format (e.g., JSONLines or a Vector DB).

## 2. Promoting Creativity and "Farfetched" Ideas

To ensure the system comes up with creative and non-obvious attack vectors, we need specific strategies:

*   **Asymmetric Contexts:** Instantiate multiple *Mastermind* agents with different information levels.
    *   *White-box Agent:* Has full access to frontend and backend code.
    *   *Grey-box Agent:* Only sees the DOM and frontend JS.
    *   *Black-box Agent:* Sees nothing, treats it purely behaviorally.
*   **Lateral Thinking Prompts:** Periodically force the Mastermind to incorporate random computer science domains into its attacks (e.g., "Design an attack using the Web Speech API," or "How can we exploit the browser's Drag and Drop API?").
*   **Evolutionary Mutation:** Take a partially successful (or interestingly failed) attack and ask the agent to "mutate" it using a high LLM temperature.
*   **Persona Prompting:** Assign personas to the generation agents, such as "The Network Specialist" (focuses on intercepting traffic) vs. "The DOM Manipulator" (focuses on JS events).

## 3. Brainstorming Attack Vectors to Bypass "No-Paste"

The goal is to insert text without physical typing. Here is a categorized list of potential vectors the system could explore or propose:

### A. DOM & JavaScript Event Manipulation (Automated)
*   **Event Spoofing:** Emulating clipboard and keyboard events (`paste`, `input`, `compositionstart`, `keydown`, `keyup`) with slightly malformed payloads to bypass the specific JS listeners that block `paste`. For example, directly setting `inputType: 'insertText'` on an input event.
*   **Property Overwriting:** Using JS to directly set the `value` or `innerHTML` / `innerText` property of the editor element, completely bypassing event listeners.
*   **Listener Removal/Mutation:** Injecting a script via DevTools Protocol to find and `removeEventListener` for the paste blockers before executing a normal paste.
*   **Drag and Drop API:** Programmatically creating a text node elsewhere on the page, selecting it, and simulating a drag-and-drop event into the editor (which often has different event paths than pasting).

### B. Browser APIs & Protocols (Automated)
*   **Chrome DevTools Protocol (CDP):** Bypassing standard browser restrictions by using CDP to simulate typing at superhuman speeds directly into the node.
*   **Autofill & Password Managers:** Creating a hidden form field that the browser's autofill populates, and then using JS to move that text into the editor.
*   **Accessibility APIs / Screen Readers:** Leveraging accessibility hooks to inject text programmatically, which browsers often treat with higher privilege than standard JS.
*   **Input Method Editors (IME):** Simulating an IME composition event where a small input sequence expands into a massive block of text.

### C. Network-Level Attacks (Automated)
*   **API Interception:** Completely ignoring the frontend UI. The agent finds the backend API endpoint responsible for saving the text (e.g., the auto-save or manual save endpoint) and sends a direct POST/PUT request with the large payload.
*   **Race Conditions:** Throttling the network (simulating slow 3G) so the page loads, but the JS defense scripts haven't executed yet, and attempting to insert text in that window.
*   **Encoding Attacks:** Trying to send enormous Unicode payloads, base64 strings, or zero-width characters that might crash the validation logic.

### D. Human-in-the-Loop & Physical/OS Vectors (Non-Automated)
*(The system outputs an SOP for the human to execute and report back)*
*   **Hardware Emulation (Rubber Ducky):** Programming a USB microcontroller to act as a keyboard and type the text at the absolute maximum speed the OS allows.
*   **Local Storage/IndexedDB Manipulation:** Having the human manually edit the browser's LocalStorage or IndexedDB (if the editor caches state locally) and refreshing the page.
*   **Cross-Device Handoff:** Using features like Apple's Universal Clipboard to paste text from an iPhone to a Mac, potentially bypassing browser-level paste events.
*   **Optical Character Recognition (OCR):** Using OS-level text insertion (like iOS Live Text from the camera) directly into the field.

## 4. Evaluation and Learning Loop

1.  **Systematic Logging:** Every attempt must be logged with its `Vector Idea`, `Code/Execution Plan`, `Trace/Logs`, and `Outcome`.
2.  **RAG for Reflection:** Before the Mastermind generates a new idea, it queries the database for similar past attempts. The prompt includes: *"You previously tried X, but it failed because Y. Propose a new idea avoiding Y."*
3.  **Success Validation:** The Judge script must be robust:
    *   Navigate to the page.
    *   Execute the attack script/SOP.
    *   Check if `text.length > Threshold`.
    *   Check if `execution_time < Max_Time`.
    *   Reload the page `page.reload()`.
    *   Check if the text is still present (validating the save mechanism worked).
