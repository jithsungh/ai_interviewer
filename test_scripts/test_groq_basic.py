import asyncio
from app.ai.llm import ProviderFactory, LLMRequest

async def test_basic_generation():
    # Create Groq provider
    provider = ProviderFactory.create_text_provider("groq")
    
    # Build request
    request = LLMRequest(
        prompt="Explain what a binary search tree is in one sentence.",
        model="llama-3.3-70b-versatile",
        temperature=0.7,
        max_tokens=100,
        timeout_seconds=30
    )
    
    # Generate text
    response = await provider.generate_text(request)
    
    # Verify response
    print(f"Success: {response.success}")
    print(f"Text: {response.text}")
    print(f"Tokens: {response.telemetry.total_tokens}")
    print(f"Latency: {response.telemetry.latency_ms}ms")
    
    assert response.success is True
    assert response.text is not None
    assert len(response.text) > 0
    assert response.telemetry.latency_ms > 0

if __name__ == "__main__":
    asyncio.run(test_basic_generation())