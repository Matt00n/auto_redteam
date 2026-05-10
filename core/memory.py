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
                    attempt_id: str = None) -> str:
        
        if not attempt_id:
            attempt_id = str(uuid.uuid4())
        
        record = {
            "attempt_id": attempt_id,
            "timestamp": datetime.now(datetime.timezone.utc).isoformat(),
            "family": family,
            "hypothesis": hypothesis,
            "assumptions": assumptions,
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
