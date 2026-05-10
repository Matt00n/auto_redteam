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
    assert evidence["return_code"] == -1
