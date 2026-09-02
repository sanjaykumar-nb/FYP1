import httpx
import json
from typing import Optional
from app.config import get_settings
from app.llm.structured import validate_against_schema

settings = get_settings()

# JSON Schema "type" keywords Groq's json_object mode does not enforce, so we
# have to state them — but only tersely. A field:type hint costs a fraction of
# what a fully expanded (and often $ref-nested) Pydantic schema costs, and
# renders with none of the markers ($defs, "properties", "additionalProperties")
# a full schema dump would — see TOK-3.
def _compact_schema_hint(schema: dict) -> str:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    parts = []
    for name, spec in props.items():
        type_hint = spec.get("type", "any")
        if "enum" in spec:
            type_hint = "enum[" + ",".join(str(v) for v in spec["enum"]) + "]"
        elif "$ref" in spec or "allOf" in spec:
            type_hint = "object"
        marker = "" if name in required else "?"
        parts.append(f"{name}{marker}:{type_hint}")
    return ", ".join(parts)


class GroqClient:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.AI_MODEL
        self.temperature = settings.AI_TEMPERATURE
        self.max_tokens = settings.AI_MAX_TOKENS
        self.timeout = settings.AI_TIMEOUT_SECONDS
        self.base_url = "https://api.groq.com/openai/v1"
    
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict,
        max_retries: int = 2,
    ) -> dict:
        """Generate structured output using Groq API.

        The full JSON Schema is never sent — only a compact field:type hint
        (T1). This is most of the schema-overhead saving described in the
        knowledge-graph token budget: ~940 tokens of indented schema per
        agent call collapses to a single short line.
        """

        schema_instruction = (
            f"\n\nRespond with a single JSON object with exactly these fields "
            f"(? = optional): {_compact_schema_hint(output_schema)}"
        )

        messages = [
            {"role": "system", "content": system_prompt + schema_instruction},
            {"role": "user", "content": user_prompt},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()

                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)

                    # Validate the RAW response before it is ever handed to a
                    # Pydantic model — see R2. A malformed response is caught
                    # here, not downstream after it has already been trusted.
                    valid, errors = validate_against_schema(parsed, output_schema)
                    if not valid:
                        raise ValueError(f"LLM response failed schema validation: {errors}")

                    return parsed

            except httpx.TimeoutException:
                if attempt == max_retries - 1:
                    raise
                continue
            except json.JSONDecodeError as e:
                if attempt == max_retries - 1:
                    raise ValueError(f"Failed to parse JSON response: {e}")
                continue
            except ValueError:
                if attempt == max_retries - 1:
                    raise
                continue
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                continue

        raise Exception("Max retries exceeded")
    
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 2,
    ) -> str:
        """Generate plain text response"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                continue
        
        raise Exception("Max retries exceeded")