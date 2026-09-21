"""Without a real API key the LLM is never called; the deterministic path answers."""

from unittest.mock import AsyncMock, patch

import pytest

import app.llm.client as client_module
from app.llm.client import GroqClient, LLMUnavailable

pytestmark = pytest.mark.mvp


@pytest.mark.parametrize("key", [None, "", "   ", "your-groq-api-key-here"])
async def test_no_real_key_means_no_network_call(monkeypatch, key):
    monkeypatch.setattr(client_module.settings, "GROQ_API_KEY", key)
    llm = GroqClient()
    assert not llm.configured

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        with pytest.raises(LLMUnavailable):
            await llm.generate_structured("system", "user", {"type": "object", "properties": {}})
        post.assert_not_called()


def test_a_real_key_is_used(monkeypatch):
    monkeypatch.setattr(client_module.settings, "GROQ_API_KEY", " gsk_example ")
    llm = GroqClient()
    assert llm.configured and llm.api_key == "gsk_example"
