from core.llm import LLMProvider

class Analyst:
    """
    Reads the raw source code and distills it into a dense Mechanism Map.
    """
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def generate_mechanism_map(self, target_files: dict) -> str:
        system_prompt = (
            "You are the Code-Reading Analyst for a red-team framework. "
            "Your job is to read raw frontend and backend source code and distill it into a 'Mechanism Map'. "
            "Do NOT summarize what the app does generally. "
            "Extract highly specific details relevant to bypassing 'paste' or text-insertion defenses:\n"
            "1. Input handlers attached to the editor and exact event listeners (including their execution order).\n"
            "2. DOM-level assertions about paste and framework abstractions that might alter event timing.\n"
            "3. Whether the defense is client-only or server-enforced (backend checks for content provenance).\n"
            "4. Sanitization, validation assumptions, feature flags, or A/B conditions.\n"
            "5. State transitions between 'editable', 'blocked', 'focused', and 'committed'.\n"
            "6. WebSocket structure or API endpoints that process input.\n"
            "Keep it dense, highly technical, and focused on vulnerabilities."
        )

        user_prompt = "Target Source Code:\n"
        for filename, content in target_files.items():
            user_prompt += f"--- {filename} ---\n{content}\n\n"

        response = self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="gpt-4o-mini"
        )
        
        return response.content
