import json
from core.llm import LLMProvider
from core.memory import Historian

class Mastermind:
    def __init__(self, llm: LLMProvider, historian: Historian, persona: str = "white-box"):
        self.llm = llm
        self.historian = historian
        self.persona = persona
        
    def generate_hypothesis(self, target_files: dict, directive: dict, mechanism_map: str = None, context_mode: str = "raw_code", feedback: str = None) -> str:
        """
        Generates a new attack hypothesis based on the memory portfolio and given persona/strategy.
        context_mode: "raw_code" or "mechanism_map"
        """
        portfolio = self.historian.retrieve_portfolio()
        
        # Override persona if planner dictates a different one
        self.persona = directive.get("persona", self.persona)
        strategy = directive.get("strategy", "novel_exploration")
        focus_area = directive.get("focus_area", "General text insertion")
        
        system_prompt = (
            "You are the Mastermind, an elite red-team agent. "
            "Your goal is to bypass a web editor defense that blocks 'pasting' of text. "
        )
        
        system_prompt += f"\nFOCUS AREA ALLOCATED BY PLANNER: {focus_area}\n"
        
        if strategy == "novel_exploration":
            system_prompt += "STRATEGY: Propose a NEW, concrete mechanism that is COMPLETELY DIFFERENT from the recent attempts in the portfolio. "
        elif strategy == "evolution":
            system_prompt += "STRATEGY: Pick a recent failed attempt from the portfolio. Explicitly state why it failed, and propose a structural MUTATION to fix it. "
        elif strategy == "recombination":
            system_prompt += "STRATEGY: Take elements from a successful attempt or diverse past attempts and COMBINE them into a new hybrid mechanism. "
        
        if feedback:
            system_prompt += f"\n\nCRITIC FEEDBACK FROM PREVIOUS ATTEMPT (YOU MUST ADDRESS THIS):\n{feedback}\n"
        
        files_to_include = {}
        if self.persona == "white-box":
            system_prompt += "\nPERSONA: White-Box. You have full system visibility. Use this to find deep logic flaws.\n"
            files_to_include = target_files
        elif self.persona == "grey-box":
            system_prompt += "\nPERSONA: Grey-Box. You only have frontend visibility. Focus on DOM, JS event hijacking, and browser features.\n"
            files_to_include = {k: v for k, v in target_files.items() if k in ["assignments.html", "home.js"]}
        else: # black-box
            system_prompt += "\nPERSONA: Black-Box. You have no code access. Focus on OS-level HID emulation, Computer Use, and timing attacks.\n"
            files_to_include = {}
            
        user_prompt = f"Memory Portfolio:\n{json.dumps(portfolio, indent=2)}\n\n"
        
        if context_mode == "mechanism_map" and mechanism_map and self.persona != "black-box":
            user_prompt += f"Target Code Mechanism Map (Condensed Analysis):\n{mechanism_map}\n\n"
        elif files_to_include:
            user_prompt += "Target Source Code:\n"
            for filename, content in files_to_include.items():
                user_prompt += f"--- {filename} ---\n{content}\n\n"
            
        user_prompt += (
            "Output your hypothesis strictly in the following JSON format:\n"
            "{\n"
            '  "critique_of_past_attempt": "If evolution/recombination, why did the past attempt fail? (If novel, put N/A)",\n'
            '  "mutation_strategy": "How are you changing the previous mechanism? (If novel, put N/A)",\n'
            '  "relations": ["attempt_id_1", "attempt_id_2"], // Put the exact attempt_ids you are mutating or recombining here. If novel, leave empty [].\n'
            '  "family": "Attack Family Name (e.g. DOM Exploit, Network Spoof)",\n'
            '  "hypothesis": "Detailed description of the new attack mechanism",\n'
            '  "assumptions": ["assumption 1", "assumption 2"],\n'
            '  "execution_mode": "automated" or "human_involved" or "computer_use"\n'
            "}"
        )
        
        response = self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="gpt-4o"
        )
        
        return response.content
