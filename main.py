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
        
    target_url = "http://localhost:8000/assignments/0de7199b-80ba-4686-839b-aacff2025cc5"
    assignment_taker_id = "0de7199b-80ba-4686-839b-aacff2025cc5"
    
    historian = Historian(log_dir="logs")
    executor = Executor(sandbox_dir="sandbox")
    
    judge = Judge(target_url=target_url)
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

    human_tasks_queue = []
    
    iterations = 5 
    for i in range(iterations):
        print(f"\n--- Iteration {i+1} ---")
        
        from agents.planner import Planner
        planner = Planner(llm=llm, historian=historian)
        
        seed_file = "seeds.json"
        seeds = []
        if os.path.exists(seed_file):
            with open(seed_file, "r") as f:
                seeds = json.load(f)
                
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
            with open(seed_file, "w") as f:
                json.dump(seeds, f, indent=2)
        else:
            print(f"[*] Planner is generating directive (Taxonomy Mode: {taxonomy_mode})...")
            
        directive = planner.generate_directive(taxonomy_mode=taxonomy_mode, seed=selected_seed)
        
        persona = directive.get("persona", "white-box")
        strategy = directive.get("strategy", "novel_exploration")
        target_browser = directive.get("target_browser", "chromium")
        focus_area = directive.get("focus_area", "General")
        reasoning = directive.get("reasoning", "")
        
        context_mode = random.choice(["raw_code", "mechanism_map"])
        
        print(f"[*] Planner Directive: Persona={persona} | Strategy={strategy}")
        print(f"    Focus Area: {focus_area}")
        print(f"    Context Mode: {context_mode}")
        print(f"    Reasoning: {reasoning}")
        
        # Programmatically sample a parent attempt for evolution/recombination strategy
        parent_attempt = None
        if strategy in ("evolution", "recombination"):
            parent_attempt = historian.sample_parent_for_mutation()
            if parent_attempt:
                print(f"[*] Programmatically selected parent attempt for mutation: {parent_attempt.get('attempt_id')} (Family: {parent_attempt.get('family')}, Score: {parent_attempt.get('result', {}).get('score', 0)})")
            else:
                print("[*] No parent attempts found to mutate, falling back to novel exploration strategy.")
                directive["strategy"] = "novel_exploration"
                strategy = "novel_exploration"
                
        # Gather families from recent failed attempts to pass as negative constraints
        all_past = historian.retrieve_past_attempts(limit=10)
        failed_families = list(set([
            a["family"] for a in all_past 
            if a.get("result", {}).get("score", 0.0) <= 0.0 and "family" in a
        ]))
        
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
                feedback=idea_feedback,
                parent_attempt=parent_attempt,
                failed_families=failed_families
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
            
        # 2. Code Generation & Critique Loop (Using cost-efficient local syntax checking)
        exploit_code = None
        code_feedback = None
        for attempt in range(3):
            print(f"[*] Hacker is writing the {execution_mode} exploit script (Attempt {attempt+1})...")
            exploit_code = hacker.write_exploit_script(
                hypothesis_raw,
                target_url=target_url,
                feedback=code_feedback,
                browser_choice=target_browser
            )
            
            # Local syntax pre-check (only for Python code)
            syntax_ok = True
            syntax_error_msg = None
            if execution_mode in ("automated", "computer_use", "direct_websocket"):
                try:
                    compile(exploit_code, "<string>", "exec")
                except SyntaxError as e:
                    syntax_ok = False
                    syntax_error_msg = f"Python Syntax Error: {e.msg} at line {e.lineno}, offset {e.offset}\nLine: {e.text}"
                    print(f"[-] Local Syntax Pre-Check Failed: {syntax_error_msg}")
            
            if not syntax_ok:
                code_feedback = f"Your generated code has a Python Syntax Error. Please fix it:\n{syntax_error_msg}"
                if attempt == 2:
                    print("[!] Max code retries reached. Proceeding with syntax error.")
                continue
            else:
                print("[+] Code syntax validation passed! Bypassing CodeCritic to save budget.")
                break
        
        # 3. State Reset (with transient retry loop)
        reset_ok = False
        max_reset_attempts = 3
        for attempt in range(max_reset_attempts):
            try:
                print(f"[*] Resetting target state (Attempt {attempt+1}/{max_reset_attempts})...")
                judge.reset_target_state(assignment_taker_id)
                reset_ok = True
                break
            except Exception as e:
                print(f"[!] Warning: Target state reset attempt {attempt+1} failed: {e}")
                if attempt < max_reset_attempts - 1:
                    import time
                    sleep_time = 5 * (attempt + 1)
                    print(f"[*] Retrying reset in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    print("[!] Critical Error: Max reset attempts reached. Sandbox is corrupted or target is offline.")
        
        if not reset_ok:
            break
        
        # 4. Execute Exploit
        print("[*] Executing Exploit in Sandbox...")
        run_id = str(uuid.uuid4())
        
        if execution_mode in ("automated", "computer_use", "direct_websocket"):
            evidence = executor.execute_python_code(exploit_code, run_id=run_id, timeout_seconds=30)
            print(f"    Return Code: {evidence['return_code']}")
            if evidence.get('timeout_triggered'):
                print("    Execution timed out.")
            
            if evidence['return_code'] != 0:
                outcome_notes = f"Script execution failed. Stderr: {evidence['stderr'][:200]}..."
                outcome_success = False
                outcome_score = 0.0
            else:
                outcome_notes = "Script executed successfully. Awaiting Judge validation."
                outcome_success = False 
                outcome_score = 0.0

            # 5. Evaluate
            if evidence.get("return_code") == 0:
                judge_report = judge.evaluate_success(assignment_taker_id)
                outcome_success = judge_report["success"]
                outcome_score = judge_report.get("score", 0.0)
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
            else:
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
                outcome_score=outcome_score,
                outcome_notes=outcome_notes,
                evidence=evidence,
                attempt_id=run_id,
                relations=relations
            )
            print(f"[+] Iteration {i+1} complete. Logged as {attempt_id}.\n")
        else:
            print("[!] Human-in-the-loop task generated. Queuing for batch handoff...")
            human_tasks_queue.append({
                "run_id": run_id,
                "family": family,
                "hypothesis": hypothesis_desc,
                "assumptions": assumptions,
                "persona": persona,
                "instructions": exploit_code,
                "relations": relations
            })

        # Process human handoff queue if full or at the end
        if len(human_tasks_queue) >= 3 or (i == iterations - 1 and len(human_tasks_queue) > 0):
            print(f"\n{'='*50}\n[HUMAN HANDOFF] {len(human_tasks_queue)} tasks require manual execution!\n{'='*50}")
            for task in human_tasks_queue:
                print(f"\n--- Task ID: {task['run_id']} ---")
                print(f"Family: {task['family']}")
                print(f"Hypothesis: {task['hypothesis']}")
                print(f"Instructions:\n{task['instructions']}\n")
                
                user_feedback = input("Did this work? (Type 'y' for success, or provide failure notes): ").strip()
                
                if user_feedback.lower() in ['y', 'yes', 'true', 'success']:
                    outcome_success = True
                    outcome_score = 1.0
                    outcome_notes = "Human reported: SUCCESS."
                else:
                    outcome_success = False
                    outcome_score = 0.0
                    outcome_notes = f"Human reported: {user_feedback}"
                    
                attempt_id = historian.log_attempt(
                    family=task["family"],
                    hypothesis=task["hypothesis"],
                    assumptions=task["assumptions"],
                    execution_mode="human_involved",
                    context_persona=task["persona"],
                    code_snippet=task["instructions"],
                    outcome_success=outcome_success,
                    outcome_score=outcome_score,
                    outcome_notes=outcome_notes,
                    evidence={"latency_seconds": 0, "human_feedback": user_feedback},
                    attempt_id=task["run_id"],
                    relations=task["relations"]
                )
                print(f"[+] Logged human attempt as {attempt_id}.")
            human_tasks_queue.clear()
            print("[HUMAN HANDOFF] Batch complete. Resuming automation...\n")

        # 7. Prune stale branches periodically
        if (i + 1) % 5 == 0:
            print("[*] Historian pruning stale branches...")
            historian.prune_stale_branches()

if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable.")
    else:
        main()
