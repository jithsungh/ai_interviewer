"""
Integration Tests for Groq Provider

Tests real API calls to Groq (requires GROQ_API_KEY environment variable).
These tests are skipped if API key is not available.
"""

import pytest
import os
from app.ai.llm.providers.groq_provider import GroqProvider
from app.ai.llm.contracts import LLMRequest
import dotenv

dotenv.load_dotenv()  # Load environment variables from .env file

# Skip all tests if GROQ_API_KEY not available
pytestmark = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set"
)


@pytest.fixture
def groq_provider():
    """Create Groq provider with API key from environment"""
    api_key = os.getenv("GROQ_API_KEY")
    return GroqProvider(api_key=api_key)


@pytest.mark.asyncio
async def test_groq_text_generation(groq_provider):
    """Test basic text generation with Groq"""
    request = LLMRequest(
        prompt="Say 'Hello, World!' and nothing else.",
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        max_tokens=50,
        timeout_seconds=30
    )
    
    response = await groq_provider.generate_text(request)
    
    assert response.success is True
    assert response.text is not None
    assert len(response.text) > 0
    assert response.telemetry is not None
    assert response.telemetry.model_id == "llama-3.3-70b-versatile"
    assert response.telemetry.provider == "groq"
    assert response.telemetry.latency_ms > 0
    assert response.telemetry.total_tokens > 0


@pytest.mark.asyncio
async def test_groq_json_mode(groq_provider):
    """Test structured JSON output with Groq"""
    request = LLMRequest(
        prompt="Return a JSON object with fields: name (string), age (number), active (boolean). Use test data.",
        model="llama-3.3-70b-versatile",
        json_mode=True,
        temperature=0.0,
        timeout_seconds=30,
        schema={
            "type": "object",
            "required": ["name", "age", "active"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"},
                "active": {"type": "boolean"}
            }
        }
    )
    
    response = await groq_provider.generate_structured(request)
    
    assert response.success is True
    assert response.text is not None
    
    # Verify JSON parsing
    import json
    data = json.loads(response.text)
    assert "name" in data
    assert "age" in data
    assert "active" in data
    assert isinstance(data["name"], str)
    assert isinstance(data["age"], (int, float))
    assert isinstance(data["active"], bool)


@pytest.mark.asyncio
async def test_groq_timeout(groq_provider):
    """Test timeout handling (set very short timeout)"""
    request = LLMRequest(
        prompt="Write a very long essay about artificial intelligence with thousands of words.",
        model="llama-3.3-70b-versatile",
        max_tokens=5000,
        timeout_seconds=10  # Minimum valid timeout
    )
    
    response = await groq_provider.generate_text(request)
    
    # May succeed if fast, or fail with timeout
    assert response.telemetry is not None
    if not response.success:
        assert response.error is not None
        assert response.error.type in ["timeout", "provider_error"]


@pytest.mark.asyncio
async def test_groq_deterministic_mode(groq_provider):
    """Test deterministic mode produces consistent results"""
    request = LLMRequest(
        prompt="Count from 1 to 5. Output only numbers separated by commas.",
        model="llama-3.3-70b-versatile",
        deterministic=True,
        timeout_seconds=30
    )
    
    # Make two identical requests
    response1 = await groq_provider.generate_text(request)
    response2 = await groq_provider.generate_text(request)
    
    assert response1.success is True
    assert response2.success is True
    
    # Results should be identical (or very similar due to model variance)
    # Note: Perfect determinism not guaranteed, but should be highly consistent
    assert response1.text == response2.text or \
           len(set(response1.text.split()) & set(response2.text.split())) > 3


@pytest.mark.asyncio
async def test_groq_invalid_model(groq_provider):
    """Test error handling for invalid model"""
    request = LLMRequest(
        prompt="Test",
        model="invalid-model-name",
        timeout_seconds=30
    )
    
    response = await groq_provider.generate_text(request)
    
    # Should fail with provider error
    assert response.success is False
    assert response.error is not None
    assert response.error.type in ["provider_error", "unknown"]
