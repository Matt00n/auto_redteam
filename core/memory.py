import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List


class Historian:
    """
    Manages the 'Vector DNA' of past attempts to ensure the system
    doesn't repeat failures and learns from previous execution.
    """

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        self.memory_file = os.path.join(log_dir, "attempts_db.jsonl")

    def log_attempt(
        self,
        family: str,
        hypothesis: str,
        assumptions: List[str],
        execution_mode: str,
        context_persona: str,
        code_snippet: str,
        outcome_success: bool,
        outcome_score: float,
        outcome_notes: str,
        evidence: Dict[str, Any] = None,
        attempt_id: str = None,
        relations: List[str] = None,
    ) -> str:

        if not attempt_id:
            attempt_id = str(uuid.uuid4())

        record = {
            "attempt_id": attempt_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "family": family,
            "hypothesis": hypothesis,
            "assumptions": assumptions,
            "relations": relations or [],
            "pruned": False,
            "context_persona": context_persona,
            "execution": {"mode": execution_mode, "code": code_snippet},
            "result": {
                "success": outcome_success,
                "score": outcome_score,
                "notes": outcome_notes,
            },
            "evidence": evidence or {},
        }

        with open(self.memory_file, "a") as f:
            f.write(json.dumps(record) + "\n")

        return attempt_id

    def retrieve_past_attempts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves past attempts to inject into the Mastermind prompt (poor man's RAG)."""
        if not os.path.exists(self.memory_file):
            return []

        attempts = []
        with open(self.memory_file, "r") as f:
            for line in f:
                if line.strip():
                    attempts.append(json.loads(line))

        # Return the most recent 'limit' attempts
        return attempts[-limit:]

    def retrieve_portfolio(self) -> Dict[str, Any]:
        """
        Returns a curated memory portfolio to prevent local-minimum looping.
        Samples past attempts biased by their numeric score.
        """
        attempts = []
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r") as f:
                for line in f:
                    if line.strip():
                        a = json.loads(line)
                        if not a.get("pruned", False):
                            attempts.append(a)

        if not attempts:
            return {"summary": "No past attempts.", "recent": [], "sampled": []}

        import random
        from collections import defaultdict

        # Build summary
        family_stats = defaultdict(lambda: {"total": 0, "success": 0})

        for a in attempts:
            fam = a.get("family", "Unknown")
            family_stats[fam]["total"] += 1
            if a.get("result", {}).get("success"):
                family_stats[fam]["success"] += 1

        summary_lines = []
        for fam, stats in family_stats.items():
            rate = (stats["success"] / stats["total"]) * 100
            summary_lines.append(
                f"Family '{fam}': {stats['total']} attempts, {rate:.0f}% success rate."
            )

        # Weighted sampling
        sampled_attempts = []
        weights = [a.get("result", {}).get("score", 0.0) + 0.05 for a in attempts]
        total = sum(weights)
        probs = [w / total for w in weights]

        sampled_indices = []
        while len(sampled_indices) < min(2, len(attempts)):
            idx = random.choices(range(len(attempts)), weights=probs, k=1)[0]
            if idx not in sampled_indices:
                sampled_indices.append(idx)
        sampled_attempts = [attempts[i] for i in sampled_indices]

        return {
            "summary": "\n".join(summary_lines),
            "recent": attempts[-1:] if attempts else [],
            "sampled": sampled_attempts,
        }

    def sample_parent_for_mutation(self) -> Any:
        """
        Samples exactly one past attempt to serve as the parent for mutation.
        Biased by success score, but retains a small probability (0.05 offset) for failures.
        """
        attempts = []
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r") as f:
                for line in f:
                    if line.strip():
                        a = json.loads(line)
                        if not a.get("pruned", False):
                            attempts.append(a)

        if not attempts:
            return None

        import random

        weights = [a.get("result", {}).get("score", 0.0) + 0.05 for a in attempts]
        total = sum(weights)
        probs = [w / total for w in weights]

        return random.choices(attempts, weights=probs, k=1)[0]

    def prune_stale_branches(self):
        """
        Marks attempts from consistently failing families as 'pruned' so they are excluded from context.
        """
        if not os.path.exists(self.memory_file):
            return

        attempts = []
        with open(self.memory_file, "r") as f:
            for line in f:
                if line.strip():
                    attempts.append(json.loads(line))

        from collections import defaultdict

        family_scores = defaultdict(list)
        for a in attempts:
            family_scores[a.get("family", "Unknown")].append(
                a.get("result", {}).get("score", 0.0)
            )

        pruned_families = set()
        for fam, scores in family_scores.items():
            # If a family has 3 or more attempts and has never scored above 0.0
            if len(scores) >= 20 and max(scores) == 0.0:
                pruned_families.add(fam)

        if not pruned_families:
            return

        # Write back with pruned flags
        with open(self.memory_file, "w") as f:
            for a in attempts:
                if a.get("family") in pruned_families:
                    a["pruned"] = True
                f.write(json.dumps(a) + "\n")
