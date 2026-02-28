"""
Output Sanitizer — Removes Sensitive Information from Sandbox Output

Strips internal paths, container IDs, host system information, and
other sensitive data from stdout/stderr before returning results.

Also handles output truncation to prevent memory exhaustion from
excessively large outputs (max 1MB).

References:
- REQUIREMENTS.md §5 (Output Sanitization)
- REQUIREMENTS.md §6 (Invariants: Filesystem Isolation)
"""

import re
from typing import Final


# Maximum output size in bytes (1MB)
MAX_OUTPUT_SIZE_BYTES: Final[int] = 1_048_576

# Truncation suffix appended when output exceeds max size
TRUNCATION_SUFFIX: Final[str] = "\n... (output truncated)"

# Patterns to sanitize from output
_INTERNAL_PATH_PATTERNS: Final[list[tuple[re.Pattern, str]]] = [
    # Remove /tmp/sandbox/ prefix
    (re.compile(r"/tmp/sandbox/"), ""),
    # Remove /tmp/ prefix
    (re.compile(r"/tmp/"), ""),
    # Remove /sandbox/ prefix
    (re.compile(r"/sandbox/"), ""),
]

_SYSTEM_INFO_PATTERNS: Final[list[tuple[re.Pattern, str]]] = [
    # Redact container IDs (64-char hex or short 12-char)
    (re.compile(r"container_id=[a-f0-9]{12,64}"), "container_id=<hidden>"),
    # Redact Docker container names
    (re.compile(r"container_name=[a-zA-Z0-9_.-]+"), "container_name=<hidden>"),
    # Redact host-like paths that might leak host information
    (re.compile(r"/var/lib/docker/[^\s]+"), "<hidden-path>"),
    # Redact kernel version strings
    (re.compile(r"Linux\s+\d+\.\d+\.\d+[^\s]*"), "Linux <hidden>"),
]


def sanitize_output(output: str) -> str:
    """
    Remove sensitive information from sandbox output.

    Applies path normalization and system info redaction.
    Does NOT truncate — use truncate_output() separately.

    Args:
        output: Raw output string from the sandbox container

    Returns:
        Sanitized output string with internal paths and system info removed
    """
    if not output:
        return output

    result = output

    # Remove internal path prefixes
    for pattern, replacement in _INTERNAL_PATH_PATTERNS:
        result = pattern.sub(replacement, result)

    # Redact system information
    for pattern, replacement in _SYSTEM_INFO_PATTERNS:
        result = pattern.sub(replacement, result)

    return result


def truncate_output(output: str, max_bytes: int = MAX_OUTPUT_SIZE_BYTES) -> str:
    """
    Truncate output to maximum size if it exceeds the limit.

    Truncation is byte-aware to prevent encoding issues.
    Appends a truncation notice when truncated.

    Args:
        output: Output string to potentially truncate
        max_bytes: Maximum allowed size in bytes (default: 1MB)

    Returns:
        Original string if within limit, or truncated string with notice
    """
    if not output:
        return output

    encoded = output.encode("utf-8", errors="replace")

    if len(encoded) <= max_bytes:
        return output

    # Reserve space for truncation suffix
    suffix_bytes = len(TRUNCATION_SUFFIX.encode("utf-8"))
    truncate_at = max_bytes - suffix_bytes

    # Truncate at byte boundary, decode safely
    truncated = encoded[:truncate_at].decode("utf-8", errors="replace")
    return truncated + TRUNCATION_SUFFIX


def sanitize_and_truncate(output: str, max_bytes: int = MAX_OUTPUT_SIZE_BYTES) -> str:
    """
    Sanitize and truncate output in a single pass.

    Applies sanitization first, then truncation.
    This is the preferred entry point for processing sandbox output.

    Args:
        output: Raw output from sandbox
        max_bytes: Maximum allowed size in bytes

    Returns:
        Sanitized and size-limited output string
    """
    sanitized = sanitize_output(output)
    return truncate_output(sanitized, max_bytes)


def safe_decode(raw_bytes: bytes) -> str:
    """
    Safely decode raw bytes to string.

    Handles binary output by using UTF-8 with replacement characters
    for invalid byte sequences.

    Args:
        raw_bytes: Raw bytes from subprocess output

    Returns:
        Decoded string (may contain replacement characters for binary data)
    """
    if not raw_bytes:
        return ""
    return raw_bytes.decode("utf-8", errors="replace")
