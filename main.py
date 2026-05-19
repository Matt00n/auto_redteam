import os
import json
import uuid
import random
from core.llm import get_llm
from core.memory import Historian
from core.executor import Executor
from agents.mastermind import Mastermind
from agents.hacker import Hacker
from agents.judge import Judge
from agents.critic import IdeaCritic, CodeCritic

def main():
    print("Starting Auto-RedTeam Evolutionary Loop...")
    
    try:
        llm = get_llm("openai")
    except ImportError as e:
        print(f"Warning: {e}. Ensure dependencies are installed. Proceeding with caution.")
        return
        
    historian = Historian(log_dir="logs")
    executor = Executor(sandbox_dir="sandbox")
    
    judge = Judge()
    idea_critic = IdeaCritic(llm=llm)
    code_critic = CodeCritic(llm=llm)
    
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

    print("[*] Analyst is parsing source code to create Mechanism Map...")
    from agents.analyst import Analyst
    analyst = Analyst(llm=llm)
    mechanism_map = analyst.generate_mechanism_map(target_files)

    assignment_taker_id = "test-123"
    
    iterations = 5 
    for i in range(iterations):
        print(f"\n--- Iteration {i+1} ---")
        
        from agents.planner import Planner
        planner = Planner(llm=llm, historian=historian)
        taxonomy_mode = random.choice(["choose", "sample", "unbound"])
        print(f"[*] Planner is generating directive (Taxonomy Mode: {taxonomy_mode})...")
        directive = planner.generate_directive(taxonomy_mode=taxonomy_mode)
        
        persona = directive.get("persona", "white-box")
        strategy = directive.get("strategy", "novel_exploration")
        focus_area = directive.get("focus_area", "General")
        reasoning = directive.get("reasoning", "")
        
        context_mode = random.choice(["raw_code", "mechanism_map"])
        
        print(f"[*] Planner Directive: Persona={persona} | Strategy={strategy}")
        print(f"    Focus Area: {focus_area}")
        print(f"    Context Mode: {context_mode}")
        print(f"    Reasoning: {reasoning}")
        
        mastermind = Mastermind(llm=llm, historian=historian, persona=persona)
        hacker = Hacker(llm=llm)
        
        # 1. Idea Generation & Critique Loop
        hypothesis_raw = None
        idea_feedback = None
        for attempt in range(3):
            print(f"[*] Mastermind is generating a hypothesis (Attempt {attempt+1})...")
            hypothesis_raw = mastermind.generate_hypothesis(
                target_files, 
                directive=directive, 
                mechanism_map=mechanism_map, 
                context_mode=context_mode, 
                feedback=idea_feedback
            )
            
            print("[*] Idea Critic evaluating...")
            portfolio = historian.retrieve_portfolio()
            critique = idea_critic.evaluate(hypothesis_raw, portfolio)
            
            if critique.get("approved", False):
                print("[+] Idea Approved by Critic!")
                break
            else:
                idea_feedback = critique.get("feedback", "Rejected.")
                print(f"[-] Idea Rejected: {idea_feedback}")
                if attempt == 2:
                    print("[!] Max idea retries reached. Proceeding anyway.")
                    
        # Parse hypothesis json
        try:
            hypothesis_data = json.loads(hypothesis_raw)
            family = hypothesis_data.get("family", "Unknown")
            hypothesis_desc = hypothesis_data.get("hypothesis", hypothesis_raw)
            execution_mode = hypothesis_data.get("execution_mode", "automated")
            assumptions = hypothesis_data.get("assumptions", [])
            relations = hypothesis_data.get("relations", [])
        except json.JSONDecodeError:
            family = "Unknown/ParseError"
            hypothesis_desc = hypothesis_raw
            execution_mode = "automated"
            assumptions = []
            relations = []
            
        # 2. Code Generation & Critique Loop
        exploit_code = None
        code_feedback = None
        for attempt in range(3):
            print(f"[*] Hacker is writing the {execution_mode} exploit script (Attempt {attempt+1})...")
            exploit_code = hacker.write_exploit_script(hypothesis_raw, feedback=code_feedback)
            
            print("[*] Code Critic evaluating...")
            code_critique = code_critic.evaluate(exploit_code, hypothesis_raw)
            
            if code_critique.get("approved", False):
                print("[+] Code Approved by Critic!")
                break
            else:
                code_feedback = code_critique.get("feedback", "Rejected.")
                print(f"[-] Code Rejected: {code_feedback}")
                if attempt == 2:
                    print("[!] Max code retries reached. Proceeding anyway.")
        
        # 3. State Reset
        try:
            print("[*] Resetting target state...")
            judge.reset_target_state(assignment_taker_id)
        except Exception as e:
            print(f"[!] Critical Error: Sandbox reset failed! {e}")
            break
        
        # 4. Execute Exploit
        print("[*] Executing Exploit in Sandbox...")
        run_id = str(uuid.uuid4())
        
        if execution_mode == "automated" or execution_mode == "computer_use":
            evidence = executor.execute_python_code(exploit_code, run_id=run_id, timeout_seconds=30)
            print(f"    Return Code: {evidence['return_code']}")
            if evidence['timeout_triggered']:
                print("    Execution timed out.")
            
            if evidence['return_code'] != 0:
                outcome_notes = f"Script execution failed. Stderr: {evidence['stderr'][:200]}..."
                outcome_success = False
            else:
                outcome_notes = "Script executed successfully. Awaiting Judge validation."
                outcome_success = False 
        else:
            evidence = {"stdout": "Manual execution required", "stderr": "", "artifact_dir": ""}
            outcome_notes = "Human-in-the-loop task generated."
            outcome_success = False

        # 5. Evaluate
        if execution_mode != "human_involved" and evidence.get("return_code") == 0:
            judge_report = judge.evaluate_success(assignment_taker_id)
            outcome_success = judge_report["success"]
            outcome_notes = judge_report["diagnostics"]
            
            # Enrich with browser logs if available
            artifact_dir = evidence.get("artifact_dir")
            if artifact_dir:
                log_path = os.path.join(artifact_dir, "browser_logs.txt")
                if os.path.exists(log_path):
                    with open(log_path, "r") as f:
                        logs = f.read().strip()
                        if logs:
                            outcome_notes += f"\n\nBrowser Logs:\n{logs}"
        elif execution_mode != "human_involved":
            # If the script crashed, still check if there are browser logs that explain the crash
            artifact_dir = evidence.get("artifact_dir")
            if artifact_dir:
                log_path = os.path.join(artifact_dir, "browser_logs.txt")
                if os.path.exists(log_path):
                    with open(log_path, "r") as f:
                        logs = f.read().strip()
                        if logs:
                            outcome_notes += f"\n\nBrowser Logs leading up to crash:\n{logs}"
            
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
            attempt_id=run_id,
            relations=relations
        )
        print(f"[+] Iteration {i+1} complete. Logged as {attempt_id}.\n")

if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable.")
    else:
        main()
