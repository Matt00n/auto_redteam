import json
import re
from typing import Any, Dict


def parse_robust_json(raw_text: str) -> Dict[str, Any]:
    if not raw_text:
        raise ValueError("Empty response received from LLM")

    clean_text = raw_text.strip()

    # Extract JSON from markdown code fences
    match = re.search(
        r"```(?:json)?\s*([\s\S]*?)\s*```",
        clean_text,
        re.IGNORECASE,
    )

    if match:
        clean_text = match.group(1).strip()

    try:
        result = json.loads(clean_text)

        # Handle double-encoded JSON
        if isinstance(result, str):
            result = json.loads(result)

        if not isinstance(result, dict):
            raise ValueError(f"Expected JSON object, got {type(result).__name__}")

        return result

    except json.JSONDecodeError:
        raise
