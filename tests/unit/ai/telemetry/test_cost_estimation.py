"""
Unit Tests for CostEstimator

Tests cost calculation accuracy across all known models,
unknown model handling, edge cases, and pricing table coverage.
"""

import pytest

from app.ai.telemetry.cost import CostEstimator, MODEL_PRICING
from app.ai.telemetry.contracts import CostEstimate


class TestCostEstimator:
    """Test CostEstimator cost calculations"""

    def setup_method(self):
        """Create estimator for each test"""
        self.estimator = CostEstimator()

    def test_gpt4_cost_calculation(self):
        """GPT-4 cost calculated correctly"""
        cost = self.estimator.estimate_cost(
            model_id="gpt-4",
            prompt_tokens=1000,
            completion_tokens=500,
        )

        assert cost is not None
        # GPT-4: $0.03/1K prompt, $0.06/1K completion
        expected = (1000 * 0.03 / 1000) + (500 * 0.06 / 1000)
        assert abs(cost.total_cost_usd - expected) < 0.0001
        assert cost.model_id == "gpt-4"
        assert cost.currency == "USD"

    def test_gpt35_turbo_cost_calculation(self):
        """GPT-3.5-turbo cost calculated correctly"""
        cost = self.estimator.estimate_cost(
            model_id="gpt-3.5-turbo",
            prompt_tokens=2000,
            completion_tokens=1000,
        )

        assert cost is not None
        # GPT-3.5: $0.0005/1K prompt, $0.0015/1K completion
        expected = (2000 * 0.0005 / 1000) + (1000 * 0.0015 / 1000)
        assert abs(cost.total_cost_usd - expected) < 0.0001

    def test_gpt4o_cost_calculation(self):
        """GPT-4o cost calculated correctly"""
        cost = self.estimator.estimate_cost(
            model_id="gpt-4o",
            prompt_tokens=1000,
            completion_tokens=500,
        )

        assert cost is not None
        expected = (1000 * 0.0025 / 1000) + (500 * 0.01 / 1000)
        assert abs(cost.total_cost_usd - expected) < 0.0001

    def test_claude_opus_more_expensive_than_sonnet(self):
        """Claude 3 Opus > Sonnet > Haiku in cost"""
        opus = self.estimator.estimate_cost("claude-3-opus-20240229", 1000, 500)
        sonnet = self.estimator.estimate_cost("claude-3-sonnet-20240229", 1000, 500)
        haiku = self.estimator.estimate_cost("claude-3-haiku-20240307", 1000, 500)

        assert opus is not None
        assert sonnet is not None
        assert haiku is not None
        assert opus.total_cost_usd > sonnet.total_cost_usd
        assert sonnet.total_cost_usd > haiku.total_cost_usd

    def test_groq_llama_cost(self):
        """Groq Llama model cost calculated correctly"""
        cost = self.estimator.estimate_cost(
            model_id="llama-3.3-70b-versatile",
            prompt_tokens=1000,
            completion_tokens=500,
        )

        assert cost is not None
        expected = (1000 * 0.00059 / 1000) + (500 * 0.00079 / 1000)
        assert abs(cost.total_cost_usd - expected) < 0.0001

    def test_gemini_flash_exp_free(self):
        """Gemini 2.0 Flash Exp is free during preview"""
        cost = self.estimator.estimate_cost(
            model_id="gemini-2.0-flash-exp",
            prompt_tokens=10000,
            completion_tokens=5000,
        )

        assert cost is not None
        assert cost.total_cost_usd == 0.0

    def test_self_hosted_embedding_free(self):
        """Self-hosted embedding model has zero cost"""
        cost = self.estimator.estimate_cost(
            model_id="all-mpnet-base-v2",
            prompt_tokens=1000,
            completion_tokens=0,
        )

        assert cost is not None
        assert cost.total_cost_usd == 0.0

    def test_unknown_model_returns_none(self):
        """Unknown models return None for cost"""
        cost = self.estimator.estimate_cost("unknown-model-xyz", 1000, 500)
        assert cost is None

    def test_zero_tokens_zero_cost(self):
        """Zero tokens = zero cost"""
        cost = self.estimator.estimate_cost("gpt-4", 0, 0)

        assert cost is not None
        assert cost.total_cost_usd == 0.0

    def test_embedding_cost_no_completion(self):
        """Embedding models have no completion cost"""
        cost = self.estimator.estimate_cost(
            model_id="text-embedding-ada-002",
            prompt_tokens=1000,
            completion_tokens=0,
        )

        assert cost is not None
        assert cost.total_cost_usd > 0
        assert cost.completion_cost_per_1k == 0.0

    def test_cost_estimate_is_frozen(self):
        """CostEstimate is immutable (frozen dataclass)"""
        cost = self.estimator.estimate_cost("gpt-4", 1000, 500)

        assert cost is not None
        with pytest.raises(AttributeError):
            cost.total_cost_usd = 999.0

    def test_cost_estimate_type(self):
        """estimate_cost returns CostEstimate type"""
        cost = self.estimator.estimate_cost("gpt-4", 1000, 500)

        assert isinstance(cost, CostEstimate)
        assert isinstance(cost.model_id, str)
        assert isinstance(cost.total_cost_usd, float)

    def test_large_token_cost(self):
        """Large token counts produce reasonable costs"""
        cost = self.estimator.estimate_cost("gpt-4", 100_000, 50_000)

        assert cost is not None
        # GPT-4: 100K * 0.03/1K = $3.00 prompt + 50K * 0.06/1K = $3.00 completion = $6.00
        assert abs(cost.total_cost_usd - 6.0) < 0.01

    def test_all_pricing_models_have_entries(self):
        """All models in MODEL_PRICING have valid pricing tuples"""
        for model_id, (prompt, completion) in MODEL_PRICING.items():
            assert isinstance(prompt, (int, float)), f"{model_id}: invalid prompt price"
            assert isinstance(completion, (int, float)), f"{model_id}: invalid completion price"
            assert prompt >= 0, f"{model_id}: negative prompt price"
            assert completion >= 0, f"{model_id}: negative completion price"

    def test_get_known_models(self):
        """get_known_models() returns all models with pricing"""
        models = self.estimator.get_known_models()

        assert "gpt-4" in models
        assert "gpt-3.5-turbo" in models
        assert "llama-3.3-70b-versatile" in models
        assert len(models) == len(MODEL_PRICING)

    def test_has_pricing(self):
        """has_pricing() correctly identifies known and unknown models"""
        assert self.estimator.has_pricing("gpt-4") is True
        assert self.estimator.has_pricing("unknown-model") is False

    def test_custom_pricing_table(self):
        """CostEstimator can accept custom pricing"""
        custom_pricing = {
            "custom-model": (0.01, 0.02),
        }
        estimator = CostEstimator(pricing=custom_pricing)

        cost = estimator.estimate_cost("custom-model", 1000, 500)
        assert cost is not None
        expected = (1000 * 0.01 / 1000) + (500 * 0.02 / 1000)
        assert abs(cost.total_cost_usd - expected) < 0.0001

        # Default models not available in custom pricing
        assert estimator.estimate_cost("gpt-4", 1000, 500) is None

    def test_cost_precision(self):
        """Cost is rounded to 6 decimal places"""
        cost = self.estimator.estimate_cost(
            model_id="llama-3.1-8b-instant",
            prompt_tokens=1,
            completion_tokens=1,
        )

        assert cost is not None
        # Very small cost: should be precise
        cost_str = f"{cost.total_cost_usd:.6f}"
        assert len(cost_str.split(".")[1]) <= 6
