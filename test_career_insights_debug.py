#!/usr/bin/env python3
import json
import sys
import asyncio

# Add the backend to the path
sys.path.insert(0, '/home/jithsungh/projects/ai-interviewer/backend')

from app.ai.llm.provider_factory import ProviderFactory
from app.ai.llm.contracts import LLMRequest
from app.config.settings import settings

async def test_insights_generation():
    provider = ProviderFactory.create_text_provider()
    
    prompt = (
        "You are a career market analyst. Return ONLY valid JSON array with exactly 5 objects. "
        "Schema: {\"role\": str, \"industryTag\": str, \"icon\": one of "
        "smart_toy|account_balance|security|school|shopping_cart|local_hospital|sports_esports|"
        "currency_bitcoin|engineering|analytics, \"skills\": [str, str], \"minPackage\": number, "
        "\"maxPackage\": number, \"growth\": int(5-30), \"trend\": \"up\"|\"stable\"|\"down\"}. "
        "Generate for industry 'Artificial Intelligence & ML' and seniority 'Intern' for Indian market salaries in LPA."
    )
    
    req = LLMRequest(
        prompt=prompt,
        model=settings.llm.llm_model_question_generation,
        temperature=0.5,
        max_tokens=1200,
        json_mode=True,
        timeout_seconds=30,
    )
    
    print(f"Provider: {provider}")
    print(f"Model: {req.model}")
    print(f"Sending request...")
    
    response = await provider.generate_structured(req)
    
    print(f"Response success: {response.success}")
    print(f"Response text:\n{response.text}")
    
    if response.error:
        print(f"Response error: {response.error}")
    
    # Try to parse it
    import re
    text = response.text
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    
    try:
        parsed = json.loads(cleaned)
        print(f"\nParsed JSON: {json.dumps(parsed, indent=2)}")
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Cleaned text:\n{cleaned}")

if __name__ == "__main__":
    asyncio.run(test_insights_generation())
