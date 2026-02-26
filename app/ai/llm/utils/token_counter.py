"""
Token Counting Utilities

Provides token estimation for prompts and responses.
Useful for quota tracking and cost estimation when provider doesn't report tokens.
"""

import re
from typing import Optional


def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Estimate token count for text.
    
    This is a rough approximation. Always prefer provider-reported token counts.
    
    Args:
        text: Text to count tokens for
        model: Model ID (affects tokenization)
    
    Returns:
        Estimated token count
    
    Approximation rules:
    - English: ~4 characters per token
    - Code: ~3 characters per token
    - Non-English: ~2 characters per token
    """
    if not text:
        return 0
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Heuristic: 4 chars per token for English text
    char_count = len(text)
    
    # Adjust for code (more tokens per char)
    if _is_code_heavy(text):
        return int(char_count / 3)
    
    # Adjust for non-English (more tokens per char)
    if _is_non_english(text):
        return int(char_count / 2)
    
    # Default: English text
    return int(char_count / 4)


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model_id: str
) -> Optional[float]:
    """
    Estimate cost in USD for LLM request.
    
    Args:
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        model_id: Model ID
    
    Returns:
        Estimated cost in USD, or None if pricing unknown
    
    Note: Pricing is approximate and may change. Use for estimation only.
    """
    pricing = _get_model_pricing(model_id)
    if not pricing:
        return None
    
    prompt_cost = (prompt_tokens / 1000) * pricing['prompt_per_1k']
    completion_cost = (completion_tokens / 1000) * pricing['completion_per_1k']
    
    return prompt_cost + completion_cost


def _get_model_pricing(model_id: str) -> Optional[dict]:
    """
    Get pricing for model.
    
    Returns:
        Dict with 'prompt_per_1k' and 'completion_per_1k' in USD
    """
    # Pricing as of Feb 2026 (approximate)
    pricing_table = {
        # OpenAI
        "gpt-4o": {"prompt_per_1k": 0.005, "completion_per_1k": 0.015},
        "gpt-4-turbo": {"prompt_per_1k": 0.01, "completion_per_1k": 0.03},
        "gpt-4": {"prompt_per_1k": 0.03, "completion_per_1k": 0.06},
        "gpt-3.5-turbo": {"prompt_per_1k": 0.0005, "completion_per_1k": 0.0015},
        
        # Anthropic
        "claude-3-5-sonnet-20241022": {"prompt_per_1k": 0.003, "completion_per_1k": 0.015},
        "claude-3-opus-20240229": {"prompt_per_1k": 0.015, "completion_per_1k": 0.075},
        "claude-3-sonnet-20240229": {"prompt_per_1k": 0.003, "completion_per_1k": 0.015},
        "claude-3-haiku-20240307": {"prompt_per_1k": 0.00025, "completion_per_1k": 0.00125},
        
        # Groq (free tier, but usage limits apply)
        "llama-3.3-70b-versatile": {"prompt_per_1k": 0.0, "completion_per_1k": 0.0},
        "llama-3.1-70b-versatile": {"prompt_per_1k": 0.0, "completion_per_1k": 0.0},
        "mixtral-8x7b-32768": {"prompt_per_1k": 0.0, "completion_per_1k": 0.0},
        
        # Gemini
        "gemini-2.0-flash-exp": {"prompt_per_1k": 0.0, "completion_per_1k": 0.0},
        "gemini-1.5-pro": {"prompt_per_1k": 0.00125, "completion_per_1k": 0.005},
        "gemini-1.5-flash": {"prompt_per_1k": 0.000075, "completion_per_1k": 0.0003},
    }
    
    return pricing_table.get(model_id)


def _is_code_heavy(text: str) -> bool:
    """Check if text is code-heavy (affects tokenization)"""
    # Heuristics: presence of code patterns
    code_indicators = [
        r'def\s+\w+\(',  # Python functions
        r'class\s+\w+',  # Class definitions
        r'function\s+\w+\(',  # JavaScript functions
        r'import\s+\w+',  # Import statements
        r'{\s*\n',  # Brace formatting
        r'=>',  # Arrow functions
        r'\w+\.\w+\(',  # Method calls
    ]
    
    code_pattern_count = sum(
        1 for pattern in code_indicators
        if re.search(pattern, text)
    )
    
    return code_pattern_count >= 3


def _is_non_english(text: str) -> bool:
    """Check if text contains significant non-ASCII characters"""
    non_ascii_count = sum(1 for char in text if ord(char) > 127)
    return non_ascii_count > len(text) * 0.3


def truncate_text(
    text: str,
    max_tokens: int,
    model: str = "gpt-4"
) -> str:
    """
    Truncate text to fit within token limit.
    
    Args:
        text: Text to truncate
        max_tokens: Maximum tokens allowed
        model: Model ID (affects tokenization)
    
    Returns:
        Truncated text
    
    Note: This is approximate. Use provider-specific tokenizers for accuracy.
    """
    estimated_tokens = estimate_tokens(text, model)
    
    if estimated_tokens <= max_tokens:
        return text
    
    # Approximate truncation ratio
    truncate_ratio = max_tokens / estimated_tokens
    truncate_chars = int(len(text) * truncate_ratio * 0.9)  # Leave buffer
    
    truncated = text[:truncate_chars]
    
    # Try to break at sentence boundary
    last_period = truncated.rfind('.')
    if last_period > truncate_chars * 0.8:
        truncated = truncated[:last_period + 1]
    
    return truncated.strip()
