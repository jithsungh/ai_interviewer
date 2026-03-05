"""
Unit Tests — Audio Persistence Exceptions

Tests for domain-specific exceptions: DuplicateAnalyticsError,
ImmutabilityError.
"""

import pytest

from app.audio.persistence.exceptions import (
    DuplicateAnalyticsError,
    ImmutabilityError,
)
from app.shared.errors.exceptions import BaseError, ConflictError


class TestDuplicateAnalyticsError:
    """Tests for DuplicateAnalyticsError."""

    def test_inherits_from_conflict_error(self):
        """Must inherit from ConflictError (HTTP 409)."""
        err = DuplicateAnalyticsError(exchange_id=42)
        assert isinstance(err, ConflictError)
        assert isinstance(err, BaseError)

    def test_error_code(self):
        """Error code is DUPLICATE_ANALYTICS."""
        err = DuplicateAnalyticsError(exchange_id=42)
        assert err.error_code == "DUPLICATE_ANALYTICS"

    def test_http_status(self):
        """HTTP status is 409."""
        err = DuplicateAnalyticsError(exchange_id=42)
        assert err.http_status_code == 409

    def test_message_includes_exchange_id(self):
        """Error message includes the exchange ID."""
        err = DuplicateAnalyticsError(exchange_id=123)
        assert "123" in err.message

    def test_metadata_contains_exchange_id(self):
        """Metadata includes exchange_id."""
        err = DuplicateAnalyticsError(exchange_id=42)
        assert err.metadata["exchange_id"] == 42

    def test_exchange_id_attribute(self):
        """Custom attribute stores exchange_id."""
        err = DuplicateAnalyticsError(exchange_id=99)
        assert err.exchange_id == 99


class TestImmutabilityError:
    """Tests for ImmutabilityError."""

    def test_inherits_from_base_error(self):
        """Must inherit from BaseError."""
        err = ImmutabilityError(analytics_id=1)
        assert isinstance(err, BaseError)

    def test_error_code(self):
        """Error code is ANALYTICS_IMMUTABLE."""
        err = ImmutabilityError(analytics_id=1)
        assert err.error_code == "ANALYTICS_IMMUTABLE"

    def test_http_status(self):
        """HTTP status is 400."""
        err = ImmutabilityError(analytics_id=1)
        assert err.http_status_code == 400

    def test_message_includes_analytics_id(self):
        """Error message includes the analytics ID."""
        err = ImmutabilityError(analytics_id=77)
        assert "77" in err.message

    def test_message_mentions_immutable(self):
        """Error message mentions immutability."""
        err = ImmutabilityError(analytics_id=1)
        assert "immutable" in err.message.lower()

    def test_metadata_contains_analytics_id(self):
        """Metadata includes analytics_id."""
        err = ImmutabilityError(analytics_id=42)
        assert err.metadata["analytics_id"] == 42

    def test_analytics_id_attribute(self):
        """Custom attribute stores analytics_id."""
        err = ImmutabilityError(analytics_id=88)
        assert err.analytics_id == 88
