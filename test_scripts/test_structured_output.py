import asyncio
import json
from app.ai.llm import ProviderFactory, LLMRequest

async def test_structured_output():
    provider = ProviderFactory.create_text_provider("groq")
    
    request = LLMRequest(
        prompt="""Generate a person profile with:
        - name (string)
        - age (number, 20-50)
        - skills (array of strings, at least 3)
        - experience_years (number)
        """,
        model="llama-3.3-70b-versatile",
        json_mode=True,
        temperature=0.0,
        timeout_seconds=30,
        schema={
            "type": "object",
            "required": ["name", "age", "skills", "experience_years"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"},
                "skills": {"type": "array"},
                "experience_years": {"type": "number"}
            }
        }
    )
    
    response = await provider.generate_structured(request)
    
    print(f"Success: {response.success}")
    print(f"Raw JSON: {response.text}")
    
    # Parse and validate JSON
    data = json.loads(response.text)
    print(f"\nParsed data:")
    print(f"  Name: {data['name']}")
    print(f"  Age: {data['age']}")
    print(f"  Skills: {data['skills']}")
    print(f"  Experience: {data['experience_years']} years")
    
    # Validate schema
    assert response.success is True
    assert "name" in data
    assert "age" in data
    assert "skills" in data
    assert isinstance(data["skills"], list)
    assert len(data["skills"]) >= 3
    
    print("\n✅ Schema validation passed")

if __name__ == "__main__":
    asyncio.run(test_structured_output())