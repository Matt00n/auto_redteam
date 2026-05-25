import os
import pytest
from core.executor import Executor

def test_execute_python_code(tmpdir):
    sandbox_dir = str(tmpdir.mkdir("sandbox"))
    executor = Executor(sandbox_dir=sandbox_dir)
    
    code = "import os; print(os.environ.get('RUN_ID'))"
    run_id = "test-run-123"
    
    evidence = executor.execute_python_code(code, run_id=run_id, timeout_seconds=5)
    
    assert evidence["return_code"] == 0
    assert "test-run-123" in evidence["stdout"]
    assert os.path.exists(evidence["artifact_dir"])
    assert evidence["execution_file"].endswith(f"exploit_{run_id}.py")

def test_execute_python_timeout(tmpdir):
    sandbox_dir = str(tmpdir.mkdir("sandbox"))
    executor = Executor(sandbox_dir=sandbox_dir)
    
    code = "import time; time.sleep(2)"
    run_id = "test-run-timeout"
    
    evidence = executor.execute_python_code(code, run_id=run_id, timeout_seconds=1)
    
    assert evidence["timeout_triggered"] is True
    assert evidence["return_code"] == 1

def test_execute_python_safety_block_module(tmpdir):
    sandbox_dir = str(tmpdir.mkdir("sandbox"))
    executor = Executor(sandbox_dir=sandbox_dir)
    
    # 1. Test blocked import
    code = "import subprocess; subprocess.run(['echo', 'hello'])"
    evidence = executor.execute_python_code(code, run_id="unsafe-import", timeout_seconds=5)
    assert evidence["return_code"] == 1
    assert "Safety Harness Blocked Execution" in evidence["stderr"]
    assert "Blocked import of dangerous module" in evidence["stderr"]
    
    # 2. Test blocked import from
    code2 = "from shutil import rmtree; rmtree('/tmp')"
    evidence2 = executor.execute_python_code(code2, run_id="unsafe-import-from", timeout_seconds=5)
    assert evidence2["return_code"] == 1
    assert "Safety Harness Blocked Execution" in evidence2["stderr"]
    assert "Blocked import from dangerous module" in evidence2["stderr"]

def test_execute_python_safety_block_builtin(tmpdir):
    sandbox_dir = str(tmpdir.mkdir("sandbox"))
    executor = Executor(sandbox_dir=sandbox_dir)
    
    code = "eval('print(123)')"
    evidence = executor.execute_python_code(code, run_id="unsafe-eval", timeout_seconds=5)
    assert evidence["return_code"] == 1
    assert "Blocked dangerous built-in: eval" in evidence["stderr"]

def test_execute_python_safety_block_attribute(tmpdir):
    sandbox_dir = str(tmpdir.mkdir("sandbox"))
    executor = Executor(sandbox_dir=sandbox_dir)
    
    code = "import os; os.system('ls')"
    evidence = executor.execute_python_code(code, run_id="unsafe-system", timeout_seconds=5)
    assert evidence["return_code"] == 1
    assert "Blocked call to dangerous attribute/method: system" in evidence["stderr"]

