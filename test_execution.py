# Temporary file to test the execution module
from core.executor import Executor
import pprint

e = Executor()
result = e.execute_python_code("print('Hello Red Team')", run_id="test-run")
pprint.pprint(result)
