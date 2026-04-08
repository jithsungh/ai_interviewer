#!/usr/bin/env python3
"""
Gemini Provider Integration Test

Run this script to verify the Gemini provider is working correctly.
Usage: python test_gemini_integration.py
"""

import asyncio
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_provider_instantiation():
    """Test 1: Can we create a Gemini provider?"""
    print("\n[TEST 1] Provider Instantiation")
    print("-" * 50)
    
    try:
        from app.ai.llm.provider_factory import ProviderFactory
        
        provider = ProviderFactory.create_text_provider("gemini")
        print(f"✅ Provider created: {provider.__class__.__name__}")
        print(f"✅ Supported models: {provider.get_supported_models()}")
        print(f"✅ Capabilities: {provider.capabilities.__dict__}")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


async def test_text_generation():
    """Test 2: Can we generate text?"""
    print("\n[TEST 2] Text Generation")
    print("-" * 50)
    
    try:
        from app.ai.llm.provider_factory import ProviderFactory
        from app.ai.llm.contracts import LLMRequest
        
        provider = ProviderFactory.create_text_provider("gemini")
        
        request = LLMRequest(
            model="gemini-1.5-flash",
            prompt="What is the capital of France? Answer in one word.",
            temperature=0.0,
            max_tokens=10,
        )
        
        response = await provider.generate_text(request)
        
        if response.success:
            print(f"✅ Request succeeded")
            print(f"   Response: {response.text.strip()}")
            print(f"   Tokens: {response.telemetry.total_tokens}")
            print(f"   Latency: {response.telemetry.latency_ms}ms")
            return True
        else:
            print(f"❌ Request failed: {response.error.message}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_structured_output():
    """Test 3: Can we generate structured JSON?"""
    print("\n[TEST 3] Structured Output (JSON Mode)")
    print("-" * 50)
    
    try:
        from app.ai.llm.provider_factory import ProviderFactory
        from app.ai.llm.contracts import LLMRequest
        
        provider = ProviderFactory.create_text_provider("gemini")
        
        schema = {
            "type": "object",
            "properties": {
                "capital": {"type": "string"},
                "country": {"type": "string"},
            },
            "required": ["capital", "country"]
        }
        
        request = LLMRequest(
            model="gemini-1.5-flash",
            prompt="What is the capital of France?",
            schema=schema,
            temperature=0.0,
        )
        
        response = await provider.generate_structured(request)
        
        if response.success:
            json_obj = json.loads(response.text)
            print(f"✅ Request succeeded")
            print(f"   JSON Response: {json.dumps(json_obj, indent=2)}")
            print(f"   Tokens: {response.telemetry.total_tokens}")
            print(f"   Latency: {response.telemetry.latency_ms}ms")
            return True
        else:
            print(f"❌ Request failed: {response.error.message}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_config_loading():
    """Test 4: Does config load Gemini model from env?"""
    print("\n[TEST 4] Config Loading from Environment")
    print("-" * 50)
    
    try:
        from app.evaluation.scoring.config import get_scoring_config
        
        config = get_scoring_config()
        print(f"✅ Config loaded")
        print(f"   Provider: {config.provider}")
        print(f"   Model: {config.model}")
        print(f"   API Key present: {len(config.api_key or '') > 0}")
        
        if config.provider == "gemini" and "gemini" in config.model:
            return True
        else:
            print(f"⚠️  Expected gemini provider, got {config.provider}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_error_handling():
    """Test 5: Does error handling work?"""
    print("\n[TEST 5] Error Handling")
    print("-" * 50)
    
    try:
        from app.ai.llm.provider_factory import ProviderFactory
        from app.ai.llm.contracts import LLMRequest
        
        provider = ProviderFactory.create_text_provider("gemini")
        
        # Test with invalid model
        request = LLMRequest(
            model="invalid-model-xyz",
            prompt="Test prompt",
        )
        
        response = await provider.generate_text(request)
        
        if not response.success:
            print(f"✅ Error caught correctly")
            print(f"   Error type: {response.error.type}")
            print(f"   Retryable: {response.error.retryable}")
            print(f"   Message: {response.error.message}")
            return True
        else:
            print(f"⚠️  Expected error, but request succeeded")
            return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("GEMINI PROVIDER INTEGRATION TESTS")
    print("="*60)
    
    results = {}
    
    # Run tests
    results["Provider Instantiation"] = await test_provider_instantiation()
    results["Text Generation"] = await test_text_generation()
    results["Structured Output"] = await test_structured_output()
    results["Config Loading"] = await test_config_loading()
    results["Error Handling"] = await test_error_handling()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*60)
    print(f"Results: {passed}/{total} tests passed")
    print("="*60 + "\n")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
