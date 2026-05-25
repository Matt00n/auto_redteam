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
        outcome_score=1.0,
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
        outcome_score=0.0,
        outcome_notes="", evidence={}, attempt_id=custom_id
    )
    
    attempts = historian.retrieve_past_attempts()
    assert attempts[0]["attempt_id"] == custom_id


def test_sample_parent_for_mutation(tmpdir):
    log_dir = str(tmpdir.mkdir("logs"))
    historian = Historian(log_dir=log_dir)
    
    # Log two attempts: one total failure (score 0.0) and one near-success (score 8.0)
    historian.log_attempt(
        family="Failure", hypothesis="F", assumptions=[], execution_mode="automated",
        context_persona="white-box", code_snippet="fail", outcome_success=False,
        outcome_score=0.0, outcome_notes="Failed", evidence={}, attempt_id="attempt-fail"
    )
    historian.log_attempt(
        family="NearSuccess", hypothesis="S", assumptions=[], execution_mode="automated",
        context_persona="white-box", code_snippet="success", outcome_success=False,
        outcome_score=8.0, outcome_notes="Near success", evidence={}, attempt_id="attempt-near"
    )
    
    # Sample multiple times to verify distribution works and respects scores
    samples = []
    for _ in range(100):
        parent = historian.sample_parent_for_mutation()
        samples.append(parent["attempt_id"])
        
    assert "attempt-near" in samples
    # Near success (weight 8.05) should dominate the failure (weight 0.05)
    assert samples.count("attempt-near") > samples.count("attempt-fail")

