import json
from core.llm import LLMProvider
from core.memory import Historian

class Mastermind:
    def __init__(self, llm: LLMProvider, historian: Historian, persona: str = "white-box"):
        self.llm = llm
        self.historian = historian
        self.persona = persona
        
    def generate_hypothesis(self, target_files: dict) -> str:
        """
        Generates a new attack hypothesis based on past attempts and the given persona context.
        target_files should be a dict like {"assignments.html": "...", "home.js": "...", "consumer.py": "..."}
        """
        past_attempts = self.historian.retrieve_past_attempts(limit=5)
        past_context = "\n".join([json.dumps(a) for a in past_attempts])
        
        system_prompt = (
            "You are the Mastermind, an elite red-team agent. "
            "Your goal is to bypass a web editor defense that blocks 'pasting' of text. "
            "You must propose a NEW, concrete, and testable mechanism to insert text. "
            "Do NOT propose something we already tried and failed. "
        )
        
        files_to_include = {}
        if self.persona == "white-box":
            system_prompt += "You have access to both frontend and backend code. Use this to find deep logic flaws.\n"
            files_to_include = target_files
        elif self.persona == "grey-box":
            system_prompt += "You have access to frontend code only. Focus on DOM, JS event hijacking, and browser features.\n"
            files_to_include = {k: v for k, v in target_files.items() if k in ["assignments.html", "home.js"]}
        else: # black-box
            system_prompt += "You have no code access. Focus on OS-level HID emulation, Computer Use, and timing attacks.\n"
            files_to_include = {}
            
        user_prompt = f"Past Attempts:\n{past_context}\n\n"
        
        if files_to_include:
            user_prompt += "Target Source Code:\n"
            for filename, content in files_to_include.items():
                user_prompt += f"--- {filename} ---\n{content}\n\n"
            
        user_prompt += (
            "Output your hypothesis strictly in the following JSON format:\n"
            "{\n"
            '  "family": "Attack Family Name (e.g. DOM Exploit, Network Spoof)",\n'
            '  "hypothesis": "Description of the attack mechanism",\n'
            '  "assumptions": ["assumption 1", "assumption 2"],\n'
            '  "execution_mode": "automated" or "human_involved" or "computer_use"\n'
            "}"
        )
        
        response = self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # Use JSON mode if supported, or rely on prompting
            model="gpt-4o"
        )
        
        # Here we would normally parse the JSON carefully. 
        # For the scaffold, we just return the raw text block or parsed dict.
        return response.content
