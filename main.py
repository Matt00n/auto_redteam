import os
import json
from core.llm import get_llm
from core.memory import Historian
from core.executor import Executor
from agents.mastermind import Mastermind
from agents.hacker import Hacker
from agents.judge import Judge

def main():
    print("Starting Auto-RedTeam Evolutionary Loop...")
    
    # Initialize components
    # Fallback to a mock LLM if keys aren't set, or wrap in try/except
    try:
        llm = get_llm("openai")
    except ImportError as e:
        print(f"Warning: {e}. Ensure dependencies are installed. Proceeding with caution.")
        return
        
    historian = Historian(log_dir="logs")
    executor = Executor(sandbox_dir="sandbox")
    
    # Decide context persona (e.g. cycle through them in a real run)
    persona = "white-box"
    mastermind = Mastermind(llm=llm, historian=historian, persona=persona)
    hacker = Hacker(llm=llm)
    judge = Judge()
    
    # Read target files from disk
    target_dir = "target"
    target_files = {}
    for filename in ["assignments.html", "home.js", "consumer.py"]:
        filepath = os.path.join(target_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                target_files[filename] = f.read()
        else:
            print(f"Warning: Could not find target file {filepath}")

    assignment_taker_id = "test-123"
    
    # The Loop
    iterations = 1 # Start small for scaffolding
    for i in range(iterations):
        print(f"--- Iteration {i+1} ---")
        
        # 1. Hypothesis Generation
        print("[*] Mastermind is generating a hypothesis...")
        hypothesis_raw = mastermind.generate_hypothesis(target_files)
        print(f"Hypothesis Output:\n{hypothesis_raw}")
        
        # Parse hypothesis json (basic fallback if it's poorly formatted)
        try:
            hypothesis_data = json.loads(hypothesis_raw)
            family = hypothesis_data.get("family", "Unknown")
            hypothesis_desc = hypothesis_data.get("hypothesis", hypothesis_raw)
            execution_mode = hypothesis_data.get("execution_mode", "automated")
            assumptions = hypothesis_data.get("assumptions", [])
        except json.JSONDecodeError:
            family = "Unknown/ParseError"
            hypothesis_desc = hypothesis_raw
            execution_mode = "automated"
            assumptions = []
        
        # 2. Execution Code Generation
        print(f"[*] Hacker is writing the {execution_mode} exploit script...")
        exploit_code = hacker.write_exploit_script(hypothesis_raw)
        
        # 3. State Reset
        judge.reset_target_state(assignment_taker_id)
        
        # 4. Execute Exploit
        print("[*] Executing Exploit in Sandbox...")
        import uuid
        run_id = str(uuid.uuid4())
        
        if execution_mode == "automated" or execution_mode == "computer_use":
            evidence = executor.execute_python_code(exploit_code, run_id=run_id, timeout_seconds=30)
            print(f"    Return Code: {evidence['return_code']}")
            if evidence['timeout_triggered']:
                print("    Execution timed out.")
            
            # Simple heuristic for failure during script execution
            if evidence['return_code'] != 0:
                outcome_notes = f"Script execution failed. Stderr: {evidence['stderr'][:100]}..."
                outcome_success = False
            else:
                outcome_notes = "Script executed successfully. Awaiting Judge validation."
                outcome_success = False # Judge decides actual success
        else:
            evidence = {"stdout": "Manual execution required", "stderr": "", "artifact_dir": ""}
            outcome_notes = "Human-in-the-loop task generated."
            outcome_success = False

        # 5. Evaluate
        if execution_mode != "human_involved" and evidence.get("return_code") == 0:
            is_success = judge.evaluate_success(assignment_taker_id)
            if is_success:
                outcome_success = True
                outcome_notes = "Exploit bypassed defenses and persisted."
            else:
                outcome_success = False
                outcome_notes = "Script ran, but Judge found no persistent text bypass."
            
        # 6. Log attempt (Vector DNA)
        print("[*] Historian logging attempt...")
        attempt_id = historian.log_attempt(
            family=family,
            hypothesis=hypothesis_desc,
            assumptions=assumptions,
            execution_mode=execution_mode,
            context_persona=persona,
            code_snippet=exploit_code,
            outcome_success=outcome_success,
            outcome_notes=outcome_notes,
            evidence=evidence,
            attempt_id=run_id
        )
        print(f"[+] Iteration {i+1} complete. Logged as {attempt_id}.\n")

if __name__ == "__main__":
    # Ensure OPENAI_API_KEY is set or the provider will fail
    if not os.environ.get("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable.")
    else:
        main()
