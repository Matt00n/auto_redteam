import json
import random
from core.llm import LLMProvider
from core.memory import Historian

class Planner:
    """
    Decides what to test next based on prior failures and portfolio.
    It allocates attention by choosing the persona, strategy, and focus area.
    """
    def __init__(self, llm: LLMProvider, historian: Historian):
        self.llm = llm
        self.historian = historian
        
        self.taxonomy_list = [
            "UI event-path mismatches (e.g. bypassing 'onpaste' but hitting 'drop')",
            "Input modality asymmetries (Drag & Drop, virtual keyboards, OS-level automation)",
            "Timing / state races (e.g. injecting right before the WebSocket initializes)",
            "Component boundary confusion (e.g. frontend blocks input, but backend layer accepts it)",
            "Human-mediated workflows (e.g. bizarre OS keyboard shortcut sequences)",
            "Recovery / undo / composition paths (e.g. IME composition events, Ctrl+Z bugs)",
            "Accessibility and assistive-technology paths (e.g. Screen reader inputs bypassing normal DOM)",
            "Cross-component side effects (e.g. other widgets leaking text into the editor)",
            "Version / environment differences (emulating outdated browsers, specific locales)",
            "CSS manipulation (e.g. pointer-events, z-index overlays to trick click targets)",
            "WebSocket state desync / Raw payload spoofing"
        ]
        
    def generate_directive(self, taxonomy_mode: str = "choose") -> dict:
        """
        taxonomy_mode: "choose", "sample", or "unbound"
        """
        portfolio = self.historian.retrieve_portfolio()
        
        system_prompt = (
            "You are the Planner Orchestrator for an automated red-team framework. "
            "Your job is to read the history of past attempts and output a high-level directive for the next test. "
            "You do not invent the specific exploit. You allocate attention to a specific attack family or mechanism. "
            "If a family has a 0% success rate after many attempts, pivot away from it. "
            "If a family shows partial success, focus on evolving it. "
        )
        
        if taxonomy_mode == "choose":
            system_prompt += "To maintain diversity, explicitly instruct the generator to look for different specific exploits. "
            system_prompt += "Here is a high-level taxonomy of exploit families to draw inspiration from:\n"
            for i, tax in enumerate(self.taxonomy_list):
                system_prompt += f"{i+1}. {tax}\n"
            system_prompt += "IMPORTANT: Do not become rigidly limited by this list! You are highly encouraged to invent entirely new taxonomy categories, or mix and recombine multiple categories together to create hybrid attack vectors.\n"
            
        elif taxonomy_mode == "sample":
            sampled = random.sample(self.taxonomy_list, random.randint(1, 3))
            system_prompt += "To force lateral thinking, your directive MUST focus on one or a combination of the following randomly sampled exploit families:\n"
            for tax in sampled:
                system_prompt += f"- {tax}\n"
            system_prompt += "You must find a way to apply these specific constraints to the current target.\n"
            
        elif taxonomy_mode == "unbound":
            system_prompt += "For this iteration, you are operating in UNBOUND EXPLORATION mode. "
            system_prompt += "Do NOT use standard web vulnerabilities like standard XSS or basic DOM manipulation. "
            system_prompt += "You must invent an entirely novel, esoteric, or out-of-the-box attack category that hasn't been categorized before.\n"

        system_prompt += (
            "Output your directive strictly as JSON:\n"
            "{\n"
            '  "persona": "white-box" | "grey-box" | "black-box",\n'
            '  "strategy": "novel_exploration" | "evolution" | "recombination",\n'
            '  "focus_area": "Detailed description of the area or mechanism to investigate",\n'
            '  "reasoning": "Why you chose this directive based on the portfolio"\n'
            "}"
        )
        
        user_prompt = f"Memory Portfolio:\n{json.dumps(portfolio, indent=2)}\n\nGenerate the next directive."
        
        response = self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="gpt-4o"
        )
        
        try:
            # We assume LLM Provider returns raw string or we extract json
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            return json.loads(content)
        except Exception:
            return {
                "persona": "white-box",
                "strategy": "novel_exploration",
                "focus_area": "Fallback: Explore any novel vector.",
                "reasoning": "Failed to parse JSON, defaulting to basic exploration."
            }
