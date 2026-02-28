"""
Unit Tests for MetricsAggregator

Tests aggregation of telemetry records including counts, tokens,
costs, latency percentiles, and error breakdowns.
"""

import pytest
from datetime import datetime

from app.ai.llm.contracts import TelemetryData
from app.ai.telemetry.aggregation import MetricsAggregator, _percentile
from app.ai.telemetry.contracts import AggregatedMetrics


def _make_telemetry(
    success: bool = True,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    latency_ms: int = 3000,
    model_id: str = "gpt-4",
    provider: str = "openai",
    error_type: str = None,
    estimated_cost_usd: float = None,
    organization_id: int = None,
) -> TelemetryData:
    """Helper to create TelemetryData for testing"""
    return TelemetryData(
        model_id=model_id,
        provider=provider,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=latency_ms,
        success=success,
        error_type=error_type,
        estimated_cost_usd=estimated_cost_usd,
        organization_id=organization_id,
    )


class TestMetricsAggregator:
    """Test MetricsAggregator aggregation logic"""

    def setup_method(self):
        self.aggregator = MetricsAggregator()

    def test_empty_records(self):
        """Empty records produce zero aggregation"""
        result = self.aggregator.aggregate([], time_period="hour")

        assert result.total_requests == 0
        assert result.successful_requests == 0
        assert result.failed_requests == 0
        assert result.total_tokens == 0
        assert result.total_cost_usd == 0.0

    def test_single_successful_record(self):
        """Single successful record aggregated correctly"""
        records = [_make_telemetry(estimated_cost_usd=0.045)]

        result = self.aggregator.aggregate(records, time_period="hour")

        assert result.total_requests == 1
        assert result.successful_requests == 1
        assert result.failed_requests == 0
        assert result.total_tokens == 150
        assert result.total_cost_usd == 0.045

    def test_hourly_aggregation(self):
        """Multiple records aggregated correctly"""
        records = [
            _make_telemetry(estimated_cost_usd=0.045)
            for _ in range(100)
        ]

        result = self.aggregator.aggregate_hourly(records)

        assert result.time_period == "hour"
        assert result.total_requests == 100
        assert result.successful_requests == 100
        assert result.failed_requests == 0
        assert result.total_tokens == 15000  # 150 * 100

    def test_daily_aggregation(self):
        """Daily aggregation with convenience method"""
        records = [_make_telemetry() for _ in range(10)]
        result = self.aggregator.aggregate_daily(records)
        assert result.time_period == "day"
        assert result.total_requests == 10

    def test_monthly_aggregation(self):
        """Monthly aggregation with convenience method"""
        records = [_make_telemetry() for _ in range(30)]
        result = self.aggregator.aggregate_monthly(records)
        assert result.time_period == "month"
        assert result.total_requests == 30

    def test_cost_aggregation(self):
        """Total cost aggregated correctly"""
        records = [
            _make_telemetry(estimated_cost_usd=0.045)
            for _ in range(100)
        ]

        result = self.aggregator.aggregate_hourly(records)

        assert abs(result.total_cost_usd - 4.5) < 0.01  # 0.045 * 100

    def test_cost_with_none_values(self):
        """Records with None cost are excluded from sum"""
        records = [
            _make_telemetry(estimated_cost_usd=0.10),
            _make_telemetry(estimated_cost_usd=None),
            _make_telemetry(estimated_cost_usd=0.20),
        ]

        result = self.aggregator.aggregate_hourly(records)
        assert abs(result.total_cost_usd - 0.30) < 0.01

    def test_mixed_success_failure(self):
        """Mixed success/failure counted correctly"""
        records = [
            _make_telemetry(success=True),
            _make_telemetry(success=True),
            _make_telemetry(success=False, error_type="timeout"),
            _make_telemetry(success=False, error_type="rate_limit"),
            _make_telemetry(success=False, error_type="timeout"),
        ]

        result = self.aggregator.aggregate_hourly(records)

        assert result.total_requests == 5
        assert result.successful_requests == 2
        assert result.failed_requests == 3
        assert result.errors_by_type == {"timeout": 2, "rate_limit": 1}

    def test_error_breakdown(self):
        """Error types broken down correctly"""
        records = [
            _make_telemetry(success=False, error_type="timeout"),
            _make_telemetry(success=False, error_type="timeout"),
            _make_telemetry(success=False, error_type="rate_limit"),
            _make_telemetry(success=False, error_type="authentication"),
            _make_telemetry(success=False, error_type="provider_error"),
            _make_telemetry(success=False, error_type="provider_error"),
            _make_telemetry(success=False, error_type="provider_error"),
        ]

        result = self.aggregator.aggregate_hourly(records)

        assert result.errors_by_type["timeout"] == 2
        assert result.errors_by_type["rate_limit"] == 1
        assert result.errors_by_type["authentication"] == 1
        assert result.errors_by_type["provider_error"] == 3

    def test_filter_by_organization(self):
        """Organization filter applied correctly"""
        records = [
            _make_telemetry(organization_id=1),
            _make_telemetry(organization_id=1),
            _make_telemetry(organization_id=2),
            _make_telemetry(organization_id=None),
        ]

        result = self.aggregator.aggregate(
            records, time_period="hour", organization_id=1
        )

        assert result.total_requests == 2
        assert result.organization_id == 1

    def test_filter_by_model(self):
        """Model filter applied correctly"""
        records = [
            _make_telemetry(model_id="gpt-4"),
            _make_telemetry(model_id="gpt-4"),
            _make_telemetry(model_id="gpt-3.5-turbo"),
        ]

        result = self.aggregator.aggregate(
            records, time_period="hour", model_id="gpt-4"
        )

        assert result.total_requests == 2
        assert result.model_id == "gpt-4"

    def test_filter_no_matching_records(self):
        """Filter with no matching records returns zero aggregation"""
        records = [_make_telemetry(organization_id=1)]

        result = self.aggregator.aggregate(
            records, time_period="hour", organization_id=999
        )

        assert result.total_requests == 0

    def test_returns_aggregated_metrics_type(self):
        """aggregate() returns AggregatedMetrics type"""
        records = [_make_telemetry()]
        result = self.aggregator.aggregate(records, time_period="hour")
        assert isinstance(result, AggregatedMetrics)


class TestLatencyPercentiles:
    """Test latency percentile calculation"""

    def setup_method(self):
        self.aggregator = MetricsAggregator()

    def test_latency_percentiles_basic(self):
        """Basic latency percentiles computed correctly"""
        latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        records = [_make_telemetry(latency_ms=lat) for lat in latencies]

        result = self.aggregator.aggregate_hourly(records)

        assert result.p50_latency_ms == 550  # Middle of 500 and 600
        assert result.p95_latency_ms >= 900
        assert result.p99_latency_ms >= 950

    def test_single_record_percentiles(self):
        """Single record: all percentiles equal to that value"""
        records = [_make_telemetry(latency_ms=500)]

        result = self.aggregator.aggregate_hourly(records)

        assert result.p50_latency_ms == 500
        assert result.p95_latency_ms == 500
        assert result.p99_latency_ms == 500

    def test_uniform_latency_percentiles(self):
        """Uniform latency: all percentiles equal"""
        records = [_make_telemetry(latency_ms=1000) for _ in range(100)]

        result = self.aggregator.aggregate_hourly(records)

        assert result.p50_latency_ms == 1000
        assert result.p95_latency_ms == 1000
        assert result.p99_latency_ms == 1000

    def test_wide_range_latencies(self):
        """Wide range latencies produce reasonable percentiles"""
        # Simulate realistic latency distribution
        latencies = (
            [100] * 50  # 50% fast
            + [1000] * 30  # 30% normal
            + [5000] * 15  # 15% slow
            + [30000] * 5  # 5% very slow
        )
        records = [_make_telemetry(latency_ms=lat) for lat in latencies]

        result = self.aggregator.aggregate_hourly(records)

        assert result.p50_latency_ms <= 1000  # Median should be fast/normal
        assert result.p95_latency_ms >= 5000  # P95 in slow range
        assert result.p99_latency_ms >= 5000  # P99 in slow/very slow range


class TestPercentileFunction:
    """Test _percentile helper function"""

    def test_empty_list(self):
        """Empty list returns 0"""
        assert _percentile([], 50) == 0

    def test_single_value(self):
        """Single value list returns that value"""
        assert _percentile([42], 50) == 42
        assert _percentile([42], 95) == 42

    def test_two_values(self):
        """Two values: p50 is interpolated"""
        result = _percentile([100, 200], 50)
        assert result == 150  # Midpoint

    def test_sorted_input_assumption(self):
        """Function assumes pre-sorted input"""
        assert _percentile([10, 20, 30, 40, 50], 50) == 30

    def test_p0_and_p100(self):
        """Edge percentiles: p0 = min, p100 = max"""
        values = [10, 20, 30, 40, 50]
        assert _percentile(values, 0) == 10
        assert _percentile(values, 100) == 50


class TestAggregatedMetricsValidation:
    """Test AggregatedMetrics invariants"""

    def test_invalid_time_period(self):
        """Invalid time_period raises ValueError"""
        with pytest.raises(ValueError, match="time_period must be one of"):
            AggregatedMetrics(time_period="week")

    def test_negative_total_requests(self):
        """Negative total_requests raises ValueError"""
        with pytest.raises(ValueError, match="total_requests cannot be negative"):
            AggregatedMetrics(time_period="hour", total_requests=-1)

    def test_negative_total_cost(self):
        """Negative total_cost_usd raises ValueError"""
        with pytest.raises(ValueError, match="total_cost_usd cannot be negative"):
            AggregatedMetrics(time_period="hour", total_cost_usd=-1.0)

    def test_valid_time_periods(self):
        """All valid time periods accepted"""
        for period in ("hour", "day", "month"):
            metrics = AggregatedMetrics(time_period=period)
            assert metrics.time_period == period
