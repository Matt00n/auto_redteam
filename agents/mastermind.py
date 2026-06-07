import json
import random

from core.llm import LLMProvider
from core.memory import Historian


class Mastermind:
    def __init__(
        self,
        llm: LLMProvider,
        historian: Historian,
        persona: str = "white-box",
        model: str = "gemma-heretic",
        editor_id: str = "textarea1",
        required_chars: int = 200,
    ):
        self.llm = llm
        self.model = model
        self.historian = historian
        self.persona = persona
        self.editor_id = editor_id
        self.required_chars = required_chars

    def generate_hypothesis(
        self,
        target_files: dict,
        directive: dict,
        mechanism_map: str = None,
        context_mode: str = "raw_code",
        feedback: str = None,
        parent_attempts: list[dict] = None,
        failed_families: list = None,
    ) -> str:
        """
        Generates a new attack hypothesis based on the memory portfolio and given persona/strategy.
        context_mode: "raw_code" or "mechanism_map"
        """
        portfolio = self.historian.retrieve_portfolio()

        # Override persona if planner dictates a different one
        self.persona = directive.get("persona", self.persona)
        strategy = directive.get("strategy", "novel_exploration")
        focus_area = directive.get("focus_area", "General text insertion")

        # Dynamic persona/role-play shifting based on focus area
        focus_lower = focus_area.lower()
        if (
            "websocket" in focus_lower
            or "spoofing" in focus_lower
            or "payload" in focus_lower
        ):
            persona_title = "Network and Protocol Auditor specializing in WebSocket validation bypass"
        elif (
            "automation" in focus_lower
            or "hid" in focus_lower
            or "keyboard" in focus_lower
            or "virtual" in focus_lower
        ):
            persona_title = "OS Automation Architect specializing in hardware interaction design (HID) emulation"
        elif "event" in focus_lower or "dom" in focus_lower or "timing" in focus_lower:
            persona_title = "Frontend Security Engineer specializing in browser event-loop processing and DOM path hijacking"
        else:
            persona_title = (
                "Elite Red-Team Mastermind specializing in logic flaw exploitation"
            )

        system_prompt = (
            f"You are the {persona_title}. "
            "Your goal is to bypass a web editor defense that blocks 'pasting' of text. "
            f"Specifically, your ultimate goal is to insert text into the editor (ID: '{self.editor_id}'). "
            f"To achieve success, at least {self.required_chars} characters must be successfully inserted and persisted."
        )

        system_prompt += f"\nFOCUS AREA ALLOCATED BY PLANNER: {focus_area}\n"

        if failed_families:
            system_prompt += (
                "\nNEGATIVE CONSTRAINTS (PROHIBITED APPROACHES):\n"
                "To ensure diversity and prevent mode collapse, you are strictly FORBIDDEN from proposing the following attack families:\n"
            )
            for f in failed_families:
                system_prompt += f"- {f}\n"
            system_prompt += (
                "You must discover and design a completely alternative attack path.\n"
            )

        if strategy == "novel_exploration":
            system_prompt += "STRATEGY: Propose a NEW, concrete mechanism that is COMPLETELY DIFFERENT from the recent attempts in the portfolio. "
        elif strategy == "evolution":
            system_prompt += "STRATEGY: Evolve the programmatically selected parent attempt. Analyze why it failed, and propose a structural MUTATION to fix or enhance it. "
        elif strategy == "recombination":
            system_prompt += "STRATEGY: Take elements from the programmatically selected parent attempts and COMBINE them into a new hybrid mechanism. "

        if feedback:
            system_prompt += f"\n\nCRITIC FEEDBACK FROM PREVIOUS ATTEMPT (YOU MUST ADDRESS THIS):\n{feedback}\n"

        files_to_include = {}
        if self.persona == "white-box":
            system_prompt += "\nPERSONA: White-Box. You have full system visibility. Use this to find deep logic flaws.\n"
            files_to_include = target_files
        elif self.persona == "grey-box":
            system_prompt += "\nPERSONA: Grey-Box. You only have frontend visibility. Focus on DOM, JS event hijacking, and browser features.\n"
            files_to_include = {
                k: v
                for k, v in target_files.items()
                if k in ["assignments.html", "home.js"]
            }
        else:  # black-box
            system_prompt += "\nPERSONA: Black-Box. You have no code access. Focus on OS-level HID emulation, and timing attacks.\n"  # Computer Use,
            files_to_include = {}

        user_prompt = "Planner Directive:\n"
        user_prompt += json.dumps(directive, indent=2) + "\n\n"

        if parent_attempts is not None:
            for parent_attempt_num, parent_attempt in enumerate(parent_attempts):
                user_prompt += f"=== Programmatically Selected Parent Attempt {parent_attempt_num + 1} ===\n"
                user_prompt += (
                    json.dumps(
                        {
                            "attempt_id": parent_attempt.get("attempt_id"),
                            "family": parent_attempt.get("family"),
                            "hypothesis": parent_attempt.get("hypothesis"),
                            # "code": parent_attempt.get("code"),
                            "result": parent_attempt.get("result"),
                            "logs": parent_attempt.get("logs"),
                        },
                        indent=2,
                    )
                    + "\n\n"
                )

        if (
            strategy == "novel_exploration"
            and random.random() > 0.5
            and portfolio.get("sampled", None)
        ):
            user_prompt += "=== Sampled Past Attempts ===\n"
            user_prompt += portfolio["sampled"] + "\n\n"
            user_prompt += "======\n"

            # has_success = False
            # if portfolio and isinstance(portfolio, dict):
            #     sampled = portfolio.get("sampled", [])
            #     for a in sampled:
            #         if a.get("result", {}).get("success"):
            #             has_success = True

            # if has_success:
            user_prompt += "IMPORTANT: If the portfolio contains a past attempt with a score larger than 0: You MUST modify the attack vector in a meaningful way, reusing the exact same vulnerability is not accepted.\n\n"

        user_prompt += f"Context Mode: {context_mode}\n"
        if (
            context_mode == "mechanism_map"
            and mechanism_map
            and self.persona != "black-box"
        ):
            user_prompt += (
                f"Target Code Mechanism Map (Condensed Analysis):\n{mechanism_map}\n\n"
            )
        elif files_to_include:
            user_prompt += "Target Source Code:\n"
            for filename, content in files_to_include.items():
                user_prompt += f"--- {filename} ---\n{content}\n\n"

        user_prompt += (
            "Output your hypothesis strictly in the following JSON format:\n"
            "{\n"
            '  "code_analysis": {\n'
            '    "brittle_assumptions": "Which assumptions in the code look brittle?",\n'
            '    "uncovered_paths": "Which code paths are not covered by the paste defense?",\n'
            '    "alternative_branches": "Which branches can be reached through a different interaction pattern?",\n'
            '    "client_enforcement_weaknesses": "Which part of the system is relying on client-side enforcement only?"\n'
            "  },\n"
            '  "critique_of_past_attempt": "If evolution/recombination, why did the past attempt fail? (If novel, put N/A)",\n'
            '  "mutation_strategy": "How are you changing the previous mechanism? (If novel, put N/A)",\n'
            '  "relations": ["attempt_id_1", "attempt_id_2"], // Put the exact attempt_ids you are mutating or recombining here. If novel, leave empty [].\n'
            '  "family": "Attack Family Name (e.g. DOM Exploit, Network Spoof)",\n'
            '  "hypothesis": "Detailed description of the new attack mechanism",\n'
            '  "assumptions": ["assumption 1", "assumption 2"],\n'
            '  "execution_mode": "automated" or "human_involved" or "computer_use" or "direct_websocket"\n'
            "}"
        )

        response = self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model,
        )

        return response.content
