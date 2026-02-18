"""
Sensitive Data Redaction

Provides utilities to redact sensitive information from logs and data structures.
Protects tokens, passwords, PII, and hidden test case outputs.
"""

from typing import Any, Set


# Sensitive field patterns to redact
SENSITIVE_FIELDS: Set[str] = {
    "access_token",
    "refresh_token",
    "password",
    "api_key",
    "secret",
    "token",
    "authorization",
    "bearer",
    "credentials",
}


def redact_sensitive_data(
    data: Any,
    redact_candidate_answers: bool = False
) -> Any:
    """
    Recursively redact sensitive fields from data structure.
    
    Redacts:
    - Access tokens, passwords, API keys
    - Hidden test case expected outputs
    - Candidate answers (if enabled)
    
    Args:
        data: Data to redact (dict, list, or primitive)
        redact_candidate_answers: If True, redact candidate_answer fields
        
    Returns:
        Redacted copy of data (deep copy with sensitive fields removed)
        
    Examples:
        >>> redact_sensitive_data({
        ...     "user_id": 42,
        ...     "access_token": "secret_token_123"
        ... })
        {"user_id": 42, "access_token": "[REDACTED]"}
        
        >>> redact_sensitive_data({
        ...     "test_case": {
        ...         "input": "[1,2,3]",
        ...         "expected_output": "6",
        ...         "is_hidden": True
        ...     }
        ... })
        {"test_case": {"input": "[1,2,3]", "expected_output": "[REDACTED]", "is_hidden": True}}
    """
    if isinstance(data, dict):
        redacted = {}

        for key, value in data.items():
            # Check if field is sensitive
            key_lower = key.lower()

            if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
                redacted[key] = "[REDACTED]"

            # Redact hidden test case expected outputs
            elif key == "expected_output" and data.get("is_hidden"):
                redacted[key] = "[REDACTED]"

            # Optionally redact candidate answers
            elif redact_candidate_answers and key == "candidate_answer":
                redacted[key] = "[REDACTED_ANSWER]"

            # Recursively redact nested structures
            else:
                redacted[key] = redact_sensitive_data(value, redact_candidate_answers)

        return redacted

    elif isinstance(data, list):
        return [redact_sensitive_data(item, redact_candidate_answers) for item in data]

    else:
        # Primitive type, return as-is
        return data


def mask_token(token: str, visible_chars: int = 4) -> str:
    """
    Mask token, showing only last N characters.
    
    Useful for logging tokens for debugging while protecting the full value.
    
    Args:
        token: Token string to mask
        visible_chars: Number of characters to show at end
        
    Returns:
        Masked token string
        
    Examples:
        >>> mask_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", 4)
        "...VCJ9"
        
        >>> mask_token("abc", 4)  # Too short
        "[REDACTED]"
    """
    if not token or len(token) <= visible_chars:
        return "[REDACTED]"

    return f"...{token[-visible_chars:]}"


def should_redact_field(field_name: str) -> bool:
    """
    Check if field should be redacted based on name.
    
    Args:
        field_name: Field name to check
        
    Returns:
        True if field should be redacted
        
    Examples:
        >>> should_redact_field("access_token")
        True
        
        >>> should_redact_field("user_id")
        False
    """
    field_lower = field_name.lower()
    return any(sensitive in field_lower for sensitive in SENSITIVE_FIELDS)
