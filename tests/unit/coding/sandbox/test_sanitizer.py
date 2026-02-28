"""
Unit Tests — Output Sanitizer

Tests path sanitization, system info redaction, output truncation,
and binary data handling.
"""

import pytest

from app.coding.sandbox.sanitizer import (
    sanitize_output,
    truncate_output,
    sanitize_and_truncate,
    safe_decode,
    MAX_OUTPUT_SIZE_BYTES,
    TRUNCATION_SUFFIX,
)


# =============================================================================
# sanitize_output Tests
# =============================================================================

class TestSanitizeOutput:
    """Tests for output sanitization (path removal, info redaction)."""

    def test_empty_string_unchanged(self):
        """Empty string passes through."""
        assert sanitize_output("") == ""

    def test_plain_text_unchanged(self):
        """Normal text without sensitive info passes through."""
        text = "Hello, World!\n42"
        assert sanitize_output(text) == text

    def test_removes_tmp_sandbox_path(self):
        """Removes /tmp/sandbox/ prefix from paths."""
        text = "/tmp/sandbox/solution.cpp:10:5: error: expected ';'"
        result = sanitize_output(text)
        assert "/tmp/sandbox/" not in result
        assert "solution.cpp:10:5: error: expected ';'" in result

    def test_removes_tmp_path(self):
        """Removes /tmp/ prefix from paths."""
        text = "File not found: /tmp/solution.py"
        result = sanitize_output(text)
        assert "/tmp/" not in result
        assert "solution.py" in result

    def test_removes_sandbox_path(self):
        """Removes /sandbox/ prefix from paths."""
        text = "Cannot open /sandbox/execute.sh"
        result = sanitize_output(text)
        assert "/sandbox/" not in result
        assert "execute.sh" in result

    def test_redacts_container_id(self):
        """Redacts container IDs (hex strings)."""
        text = "container_id=a1b2c3d4e5f6a1b2c3d4e5f6"
        result = sanitize_output(text)
        assert "container_id=<hidden>" in result
        assert "a1b2c3d4" not in result

    def test_redacts_container_name(self):
        """Redacts container names."""
        text = "container_name=sandbox-cpp-12345"
        result = sanitize_output(text)
        assert "container_name=<hidden>" in result

    def test_redacts_docker_internal_paths(self):
        """Redacts Docker internal paths."""
        text = "Error at /var/lib/docker/overlay2/abc123/merged/tmp"
        result = sanitize_output(text)
        assert "/var/lib/docker/" not in result
        assert "<hidden-path>" in result

    def test_redacts_kernel_version(self):
        """Redacts kernel version strings."""
        text = "Linux 5.15.0-76-generic"
        result = sanitize_output(text)
        assert "Linux <hidden>" in result
        assert "5.15.0" not in result

    def test_multiple_sanitizations_in_single_output(self):
        """Multiple sensitive items are all sanitized."""
        text = (
            "/tmp/sandbox/solution.cpp:1: error\n"
            "container_id=deadbeefdeadbeef\n"
            "Linux 5.15.0-76-generic\n"
        )
        result = sanitize_output(text)
        assert "/tmp/sandbox/" not in result
        assert "deadbeef" not in result
        assert "5.15.0" not in result

    def test_preserves_normal_error_messages(self):
        """Normal compilation/runtime errors are preserved."""
        text = "NameError: name 'undefined_var' is not defined"
        result = sanitize_output(text)
        assert result == text


# =============================================================================
# truncate_output Tests
# =============================================================================

class TestTruncateOutput:
    """Tests for output truncation."""

    def test_empty_string_unchanged(self):
        """Empty string is not truncated."""
        assert truncate_output("") == ""

    def test_short_string_unchanged(self):
        """Short string within limit is unchanged."""
        text = "Hello, World!"
        assert truncate_output(text) == text

    def test_exact_limit_unchanged(self):
        """String exactly at limit is unchanged."""
        text = "a" * MAX_OUTPUT_SIZE_BYTES
        assert truncate_output(text) == text

    def test_over_limit_is_truncated(self):
        """String over limit is truncated with suffix."""
        text = "a" * (MAX_OUTPUT_SIZE_BYTES + 1000)
        result = truncate_output(text)
        assert len(result.encode("utf-8")) <= MAX_OUTPUT_SIZE_BYTES
        assert result.endswith(TRUNCATION_SUFFIX)

    def test_custom_max_bytes(self):
        """Custom max_bytes parameter works."""
        text = "Hello, World! This is a test."
        result = truncate_output(text, max_bytes=10)
        assert result.endswith(TRUNCATION_SUFFIX)

    def test_truncation_is_byte_aware(self):
        """Truncation handles multi-byte UTF-8 characters."""
        # Each emoji is 4 bytes in UTF-8
        text = "\U0001f600" * 1000  # 4000 bytes
        result = truncate_output(text, max_bytes=100)
        # Should not crash and should be valid UTF-8
        result.encode("utf-8")

    def test_truncation_suffix_content(self):
        """Truncation suffix is the expected message."""
        text = "a" * 10000
        result = truncate_output(text, max_bytes=100)
        assert "output truncated" in result


# =============================================================================
# sanitize_and_truncate Tests
# =============================================================================

class TestSanitizeAndTruncate:
    """Tests for the combined sanitize + truncate pipeline."""

    def test_sanitizes_then_truncates(self):
        """Sanitization happens before truncation."""
        # Make a long string with sensitive data at the start
        text = "/tmp/sandbox/solution.py: " + "x" * (MAX_OUTPUT_SIZE_BYTES + 1000)
        result = sanitize_and_truncate(text)
        assert "/tmp/sandbox/" not in result
        assert result.endswith(TRUNCATION_SUFFIX)

    def test_short_clean_output_unchanged(self):
        """Short clean output passes through unchanged."""
        text = "42\n"
        assert sanitize_and_truncate(text) == text


# =============================================================================
# safe_decode Tests
# =============================================================================

class TestSafeDecode:
    """Tests for safe byte decoding."""

    def test_empty_bytes_returns_empty_string(self):
        """Empty bytes returns empty string."""
        assert safe_decode(b"") == ""

    def test_none_returns_empty_string(self):
        """None-like input returns empty string."""
        assert safe_decode(b"") == ""

    def test_valid_utf8_decoded(self):
        """Valid UTF-8 bytes are decoded correctly."""
        assert safe_decode(b"Hello, World!") == "Hello, World!"

    def test_invalid_bytes_replaced(self):
        """Invalid byte sequences produce replacement characters."""
        raw = b"Hello \x80\x81 World"
        result = safe_decode(raw)
        assert "Hello" in result
        assert "World" in result
        assert "\ufffd" in result  # Replacement character

    def test_binary_data_handled(self):
        """Pure binary data doesn't crash."""
        raw = bytes(range(256))
        result = safe_decode(raw)
        assert isinstance(result, str)

    def test_null_bytes_handled(self):
        """Null bytes in output are handled."""
        raw = b"output\x00with\x00nulls"
        result = safe_decode(raw)
        assert "output" in result
        assert "with" in result
