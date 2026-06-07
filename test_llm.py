import json
import os
import random

from core.llm import LLMProvider, get_llm
from core.memory import Historian
from core.utils import parse_robust_json


class Planner:
    """
    Decides what to test next based on prior failures and portfolio.
    It allocates attention by choosing the persona, strategy, and focus area.
    """

    def __init__(
        self,
        llm: LLMProvider,
        historian: Historian,
        model: str = "gemma-heretic",
    ):
        self.llm = llm
        self.model = model
        self.historian = historian

        self.taxonomy_list = [
            "WebSocket state desync / Raw payload spoofing (bypassing the frontend entirely, rate-limit-aware keystroke pacing)",
            "UI event-path mismatches (e.g. bypassing 'onpaste' but hitting 'drop')",
            "Input modality asymmetries (Drag & Drop, virtual keyboards, OS-level automation)",
            "Timing / state races (e.g. injecting right before the WebSocket initializes)",
            "Component boundary confusion (e.g. frontend blocks input, but backend layer accepts it)",
            "Human-mediated workflows (e.g. bizarre OS keyboard shortcut sequences)",
            "Recovery / undo / composition paths (e.g. IME composition events, Ctrl+Z bugs)",
            "Accessibility and assistive-technology paths (e.g. Screen reader inputs bypassing normal DOM)",
            "Cross-component side effects (e.g. other widgets leaking text into the editor)",
            "CSS manipulation (e.g. pointer-events, z-index overlays to trick click targets)",
        ]

    def generate_directive(
        self, taxonomy_mode: str = "choose", seed: dict = None
    ) -> dict:
        """
        taxonomy_mode: "choose", "sample", "unbound", "seed", or "random"
        """
        portfolio = self.historian.retrieve_portfolio()

        # Check for stagnation / lack of progress in the last 3 attempts
        all_past = self.historian.retrieve_past_attempts(limit=10)
        recent_scores = [a.get("result", {}).get("score", 0.0) for a in all_past[-3:]]
        stagnant = (
            len(recent_scores) >= 3
            and all(s <= 0.0 for s in recent_scores)
            and random.random() > 0.8
        )

        system_prompt = (
            "You are the Planner Orchestrator for an automated red-team framework. "
            "Your job is to read the history of past attempts and output a high-level directive for the next test. "
            "You do not invent the specific exploit. You allocate attention to a specific attack family or mechanism. "
            # "If a family has a 0% success rate after many attempts, pivot away from it. "
            # "If a family shows partial success, focus on evolving it. "
        )

        if stagnant:
            # Force novel exploration and force using a randomly selected taxonomy element
            forced_taxonomy = random.choice(self.taxonomy_list)
            system_prompt += (
                "\nWARNING: The last 3 attempts have failed to make progress (all scores = 0.0).\n"
                "To prevent local-optimum stagnation (mode collapse), you MUST operate in HIGH-ENTROPY NOVEL EXPLORATION mode.\n"
                f"You MUST set the strategy parameter to 'novel_exploration' and target the following specific attack family:\n"
                f"- {forced_taxonomy}\n"
                "Reject any thoughts of evolving current unsuccessful attempts. Focus entirely on starting this fresh branch.\n"
            )

        if taxonomy_mode == "seed" and seed:
            system_prompt += (
                "For this iteration, you are operating in SEED INJECTION mode. "
            )
            system_prompt += "You MUST strictly direct the Mastermind to implement the following high-value seed idea:\n"
            system_prompt += f"- Family: {seed['family']}\n"
            system_prompt += f"- Idea: {seed['description']}\n"
            system_prompt += "Your directive should enforce this exact approach to bootstrap the evolutionary tree.\n"

        elif not stagnant and taxonomy_mode == "choose":
            system_prompt += "To maintain diversity, explicitly instruct the generator to look for different specific exploits. "
            system_prompt += "Here is a high-level taxonomy of exploit families to draw inspiration from:\n"
            for i, tax in enumerate(self.taxonomy_list):
                system_prompt += f"{i + 1}. {tax}\n"
            system_prompt += "IMPORTANT: Do not become rigidly limited by this list! You are highly encouraged to invent entirely new taxonomy categories, or mix and recombine multiple categories together to create hybrid attack vectors.\n"

        elif not stagnant and taxonomy_mode == "sample":
            num_to_sample = random.randint(1, 3)
            sampled = random.sample(self.taxonomy_list, num_to_sample)
            system_prompt += f"To force lateral thinking, your directive MUST focus on {'a combination of' if num_to_sample > 1 else ''} the followign randomly sampled exploit {'families' if num_to_sample > 1 else 'family'}:\n"
            for tax in sampled:
                system_prompt += f"- {tax}\n"
            system_prompt += "You must find a way to apply these specific constraints to the current target.\n"

        elif not stagnant and taxonomy_mode == "unbound":
            system_prompt += (
                "For this iteration, you are operating in UNBOUND EXPLORATION mode. "
            )
            system_prompt += "Do NOT use standard web vulnerabilities like standard XSS or basic DOM manipulation. "
            system_prompt += "You must invent an entirely novel, esoteric, or out-of-the-box attack category that hasn't been categorized before.\n"

        system_prompt += (
            "Output your directive strictly as JSON:\n"
            "{\n"
            '  "persona": "white-box" | "grey-box" | "black-box",\n'
            '  "strategy": "novel_exploration" | "evolution" | "recombination",\n'
            '  "target_browser": "chromium" | "firefox" | "webkit" | "random",\n'
            '  "focus_area": "Detailed description of the area or mechanism to investigate",\n'
            '  "reasoning": "Why you chose this directive based on the portfolio"\n'
            "}"
        )

        # user_prompt = f"Memory Portfolio:\n{json.dumps(portfolio, indent=2)}\n\nGenerate the next directive."
        user_prompt = "====== Portfolio of sampled past attempts ======\n"
        user_prompt += f"Summary: {portfolio['summary']}\n\n{portfolio['sampled']}\n\n"
        user_prompt += "====== End of Portfolio ======\n\nGenerate the next directive."
        # user_prompt = "Generate the next directive."

        response = self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model,
        )
        # print(len(str(json.dumps(portfolio, indent=2))))
        # for k, v in portfolio.items():
        #     print(k, ":")
        #     if isinstance(v, dict):
        #         for k_1, v_1 in v.items():
        #             print(k_1, ":")
        #             if isinstance(v_1, dict):
        #                 for k_2, v_2 in v_1.items():
        #                     print(k_2, ":")
        #                     print(v_2)
        #             else:
        #                 print(v_1)
        #     elif isinstance(v, list):
        #         for el in v:
        #             for k_1, v_1 in el.items():
        #                 print(k_1, ":")
        #                 if isinstance(v_1, dict):
        #                     for k_2, v_2 in v_1.items():
        #                         print(k_2, ":")
        #                         print(v_2)
        #                 else:
        #                     print(v_1)
        #     else:
        #         print(v)

        try:
            # We assume LLM Provider returns raw string or we extract json
            content = response.content
            return parse_robust_json(content)
        except Exception:
            try:
                print(
                    f"\tError trying to extract JSON from Planner response: {response.content}"
                )
            except Exception:
                pass
            return "fail"


def main():

    try:
        llm = get_llm("openai")
    except ImportError as e:
        print(
            f"Warning: {e}. Ensure dependencies are installed. Proceeding with caution."
        )
        return

    historian = Historian(log_dir="logs")

    planner = Planner(llm=llm, historian=historian)

    seed_file = "seeds.json"
    seeds = []
    if os.path.exists(seed_file):
        with open(seed_file, "r") as f:
            seeds = json.load(f)

    for i in range(10):
        print(f"iteration {i + 1}")

        unused_seeds = [s for s in seeds if not s.get("used", False)]
        available_modes = ["choose", "sample", "unbound"]
        if unused_seeds:
            # Add seed mode, potentially weighted to happen often if many seeds exist
            available_modes.append("seed")

        taxonomy_mode = random.choice(available_modes)

        selected_seed = None
        if taxonomy_mode == "seed":
            selected_seed = random.choice(unused_seeds)
            print(f"[*] Planner is injecting SEED IDEA: {selected_seed['family']}")
            for s in seeds:
                if s["id"] == selected_seed["id"]:
                    s["used"] = True
            # with open(seed_file, "w") as f:
            #     json.dump(seeds, f, indent=2)
        else:
            print(
                f"[*] Planner is generating directive (Taxonomy Mode: {taxonomy_mode})..."
            )

        directive = planner.generate_directive(
            taxonomy_mode=taxonomy_mode, seed=selected_seed
        )
        print(directive) if directive == "fail" else print("success")
        # print(directive)


if __name__ == "__main__":
    main()
