from ai_service.app.models.agent_base import AgentOutput
from ai_service.app.models.agent_base import (
    PlanningOutput, ProgressOutput, MeetingIntelOutput,
    CommIntelOutput, WorkloadIntelOutput, RiskOutput,
    RecommendationOutput, CoordinatorOutput, ReviewTrioOutput,
)


AGENT_SCHEMAS = {
    "planning": PlanningOutput.model_json_schema(),
    "progress": ProgressOutput.model_json_schema(),
    "meeting_intelligence": MeetingIntelOutput.model_json_schema(),
    "communication_intelligence": CommIntelOutput.model_json_schema(),
    "workload_intelligence": WorkloadIntelOutput.model_json_schema(),
    "risk_prediction": RiskOutput.model_json_schema(),
    "recommendation": RecommendationOutput.model_json_schema(),
    "coordinator": CoordinatorOutput.model_json_schema(),
    "frontend_review": AgentOutput.model_json_schema(),
    "backend_review": AgentOutput.model_json_schema(),
    "ai_ml_review": AgentOutput.model_json_schema(),
    "review_trio": ReviewTrioOutput.model_json_schema(),
}


def get_schema(agent_name: str) -> dict:
    """Get JSON schema for an agent by name"""
    return AGENT_SCHEMAS.get(agent_name, AgentOutput.model_json_schema())


def validate_output(agent_name: str, output: dict) -> tuple[bool, list[str]]:
    """Validate agent output against schema (simplified)"""
    schema = get_schema(agent_name)
    errors = []
    
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    
    for field in required:
        if field not in output:
            errors.append(f"Missing required field: {field}")
    
    for field, value in output.items():
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
            
            # Check enum constraints
            if "enum" in prop_schema and value not in prop_schema["enum"]:
                errors.append(f"Field '{field}' must be one of {prop_schema['enum']}")
    
    # Agent-specific validations
    if agent_name in ["planning", "progress", "meeting_intelligence", "communication_intelligence", 
                      "workload_intelligence", "risk_prediction", "recommendation", "coordinator"]:
        # Check risk_level enum
        if "risk_level" in output:
            valid_levels = ["low", "medium", "high", "critical"]
            if output["risk_level"] not in valid_levels:
                errors.append(f"risk_level must be one of {valid_levels}")
        
        # Check confidence range
        if "confidence" in output:
            conf = output["confidence"]
            if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
                errors.append("confidence must be a number between 0 and 1")
    
    return len(errors) == 0, errors