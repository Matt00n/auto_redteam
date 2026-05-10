import os
import json
import pytest
from core.memory import Historian

def test_historian_logging(tmpdir):
    # Use tmpdir for isolated logging
    log_dir = str(tmpdir.mkdir("logs"))
    historian = Historian(log_dir=log_dir)
    
    attempt_id = historian.log_attempt(
        family="Test Family",
        hypothesis="Test Hypothesis",
        assumptions=["A1"],
        execution_mode="automated",
        context_persona="white-box",
        code_snippet="print('test')",
        outcome_success=True,
        outcome_notes="Worked perfectly",
        evidence={"stdout": "test"}
    )
    
    assert attempt_id is not None
    
    attempts = historian.retrieve_past_attempts()
    assert len(attempts) == 1
    
    record = attempts[0]
    assert record["attempt_id"] == attempt_id
    assert record["family"] == "Test Family"
    assert record["result"]["success"] is True

def test_historian_provided_id(tmpdir):
    log_dir = str(tmpdir.mkdir("logs"))
    historian = Historian(log_dir=log_dir)
    custom_id = "custom-123"
    
    historian.log_attempt(
        family="Test", hypothesis="", assumptions=[], execution_mode="automated",
        context_persona="white-box", code_snippet="", outcome_success=False,
        outcome_notes="", evidence={}, attempt_id=custom_id
    )
    
    attempts = historian.retrieve_past_attempts()
    assert attempts[0]["attempt_id"] == custom_id
