import httpx
import json
from typing import Optional
from ai_service.app.config import get_settings

settings = get_settings()


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
        """Generate structured output using Groq API"""
        
        # Add schema instruction to system prompt
        schema_instruction = f"\n\nYou must respond with valid JSON that matches this schema:\n{json.dumps(output_schema, indent=2)}"
        
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
                    return json.loads(content)
            
            except httpx.TimeoutException:
                if attempt == max_retries - 1:
                    raise
                continue
            except json.JSONDecodeError as e:
                if attempt == max_retries - 1:
                    raise ValueError(f"Failed to parse JSON response: {e}")
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