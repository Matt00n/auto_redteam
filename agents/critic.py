import json

from core.llm import LLMProvider


class IdeaCritic:
    def __init__(self, llm: LLMProvider, model: str = "gemma-heretic"):
        self.llm = llm
        self.model = model

    def evaluate(self, hypothesis_raw: str, portfolio: dict) -> dict:
        """
        Evaluates the Mastermind's hypothesis for novelty and logic.
        """
        system_prompt = (
            "You are the Idea Critic, an elite red-team peer reviewer. "
            "Your job is to read a proposed attack hypothesis and the portfolio of past attempts. "
            "Reject the idea if it is highly repetitive of a past failure without meaningful mutation. "
            "Reject the idea if it fundamentally misunderstands the web architecture or target code constraints. "
            "Approve the idea if it is genuinely novel, or a smart, explicit evolution of a past idea. "
            "Output your evaluation strictly as JSON:\n"
            "{\n"
            '  "approved": true/false,\n'
            '  "feedback": "Detailed explanation of why it was approved or rejected. If rejected, provide a hint on what to change."\n'
            "}"
        )

        user_prompt = f"Memory Portfolio:\n{json.dumps(portfolio, indent=2)}\n\nProposed Hypothesis:\n{hypothesis_raw}"

        response = self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model,
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback
            return {
                "approved": True,
                "feedback": "Failed to parse JSON, defaulting to approved.",
            }


class CodeCritic:
    def __init__(
        self,
        llm: LLMProvider,
        model: str = "gemma-heretic",
        editor_id: str = "textarea1",
        required_chars: int = 200,
    ):
        self.llm = llm
        self.model = model
        self.editor_id = editor_id
        self.required_chars = required_chars

    def evaluate(self, script_code: str, hypothesis_raw: str) -> dict:
        """
        Evaluates the Hacker's generated script against the hypothesis and general syntax/rules.
        """
        system_prompt = (
            "You are the Code Critic. Your job is to review Python/Playwright execution scripts before they run in the sandbox. "
            "Criteria for REJECTION:\n"
            "- The script does not actually implement the proposed hypothesis.\n"
            "- The script has obvious Python syntax errors.\n"
            "- If it uses Playwright, it forgets to target 'http://127.0.0.1:8000' or forgets to wait for network/element readiness.\n"
            "- It does not use the provided RUN_ID or ARTIFACT_DIR environment variables if tracing is needed.\n"
            f"- The script does not attempt to insert at least {self.required_chars} characters into the target editor (ID: '{self.editor_id}'). You MUST verify that the script's payload contains/inserts at least this many characters.\n"
            "Output your evaluation strictly as JSON:\n"
            "{\n"
            '  "approved": true/false,\n'
            '  "feedback": "Detailed explanation. If rejected, tell the Hacker exactly what lines to fix."\n'
            "}"
        )

        user_prompt = f"Hypothesis to Implement:\n{hypothesis_raw}\n\nGenerated Script:\n```python\n{script_code}\n```"

        response = self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model,
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {
                "approved": True,
                "feedback": "Parse error, defaulting to approved.",
            }
