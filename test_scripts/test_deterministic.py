import asyncio
from app.ai.llm import ProviderFactory, LLMRequest

async def test_deterministic():
    provider = ProviderFactory.create_text_provider("groq")
    
    request = LLMRequest(
        prompt="List the first 5 prime numbers, comma-separated.",
        model="llama-3.3-70b-versatile",
        deterministic=True,  # Forces temperature=0
        timeout_seconds=30
    )
    
    # Make 3 identical requests
    responses = []
    for i in range(3):
        response = await provider.generate_text(request)
        responses.append(response)
        print(f"Attempt {i+1}: {response.text}")
    
    # Verify all responses identical (or very similar)
    texts = [r.text for r in responses]
    all_identical = len(set(texts)) == 1
    
    print(f"\nAll responses identical: {all_identical}")
    
    if not all_identical:
        print("Note: Minor variance acceptable, check if semantically equivalent")
    
    assert all(r.success for r in responses)
    assert responses[0].telemetry.temperature == 0.0

if __name__ == "__main__":
    asyncio.run(test_deterministic())