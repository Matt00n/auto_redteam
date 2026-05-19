import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List


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

    def log_attempt(self, 
                    family: str, 
                    hypothesis: str, 
                    assumptions: List[str], 
                    execution_mode: str, 
                    context_persona: str,
                    code_snippet: str,
                    outcome_success: bool,
                    outcome_notes: str,
                    evidence: Dict[str, Any] = None,
                    attempt_id: str = None,
                    relations: List[str] = None) -> str:
        
        if not attempt_id:
            attempt_id = str(uuid.uuid4())
        
        record = {
            "attempt_id": attempt_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "family": family,
            "hypothesis": hypothesis,
            "assumptions": assumptions,
            "relations": relations or [],
            "context_persona": context_persona,
            "execution": {
                "mode": execution_mode,
                "code": code_snippet
            },
            "result": {
                "success": outcome_success,
                "notes": outcome_notes
            },
            "evidence": evidence or {}
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
        Returns a curated memory portfolio to prevent local-minimum looping:
        - summary: counts of explored families and success rates
        - recent: the 2 most recent attempts
        - successful: 1 random successful attempt (if any)
        - diverse: 1 random attempt from a less explored family
        """
        attempts = []
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r") as f:
                for line in f:
                    if line.strip():
                        attempts.append(json.loads(line))
                        
        if not attempts:
            return {"summary": "No past attempts.", "recent": [], "successful": [], "diverse": []}
            
        # Build summary
        family_stats = defaultdict(lambda: {"total": 0, "success": 0})
        successful_attempts = []
        
        for a in attempts:
            fam = a.get("family", "Unknown")
            family_stats[fam]["total"] += 1
            if a.get("result", {}).get("success"):
                family_stats[fam]["success"] += 1
                successful_attempts.append(a)
                
        summary_lines = []
        for fam, stats in family_stats.items():
            rate = (stats["success"] / stats["total"]) * 100
            summary_lines.append(f"Family '{fam}': {stats['total']} attempts, {rate:.0f}% success rate.")
            
        recent = attempts[-2:]
        
        successful_sample = random.sample(successful_attempts, 1) if successful_attempts else []
        
        # Diverse sample: pick from a family that isn't the most recently used
        recent_family = recent[-1].get("family") if recent else None
        diverse_candidates = [a for a in attempts if a.get("family") != recent_family]
        diverse_sample = random.sample(diverse_candidates, 1) if diverse_candidates else []
        
        return {
            "summary": "\n".join(summary_lines),
            "recent": recent,
            "successful": successful_sample,
            "diverse": diverse_sample
        }
