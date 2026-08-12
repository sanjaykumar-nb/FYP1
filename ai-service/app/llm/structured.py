import json
import re
from typing import Optional


def parse_structured_output(content: str, schema: dict) -> dict:
    """Parse and validate structured output from LLM"""
    
    # Try direct JSON parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON object in text
    json_match = re.search(r'(\{.*\})', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    raise ValueError("Could not parse structured output from LLM response")


def validate_against_schema(data: dict, schema: dict) -> tuple[bool, list[str]]:
    """Validate data against JSON schema (simplified)"""
    errors = []
    
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    for field, value in data.items():
        if field in properties:
            prop_schema = properties[field]
            expected_type = prop_schema.get("type")
            
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Field '{field}' should be string")
            elif expected_type == "number" and not isinstance(value, (int, float)):
                errors.append(f"Field '{field}' should be number")
            elif expected_type == "boolean" and not isinstance(value, bool):
                errors.append(f"Field '{field}' should be boolean")
            elif expected_type == "array" and not isinstance(value, list):
                errors.append(f"Field '{field}' should be array")
            elif expected_type == "object" and not isinstance(value, dict):
                errors.append(f"Field '{field}' should be object")
    
    return len(errors) == 0, errors