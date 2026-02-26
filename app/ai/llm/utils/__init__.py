"""
Timeout Utilities

Provides timeout enforcement for LLM provider calls.
Ensures timeouts are enforced at HTTP client level, not just SDK level.
"""

import asyncio
import httpx
from typing import Callable, TypeVar, Any
from functools import wraps
from ..errors import LLMTimeoutError

T = TypeVar('T')


def with_timeout(timeout_seconds: int, provider_name: str):
    """
    Decorator to enforce timeout on async functions.
    
    Args:
        timeout_seconds: Timeout in seconds
        provider_name: Provider name for error messages
    
    Raises:
        LLMTimeoutError: If function exceeds timeout
    
    Usage:
        @with_timeout(timeout_seconds=30, provider_name="groq")
        async def call_provider():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                raise LLMTimeoutError(
                    provider=provider_name,
                    timeout_seconds=timeout_seconds
                )
        return wrapper
    return decorator


def create_http_client(
    timeout_seconds: int = 60,
    max_retries: int = 3,
    **kwargs
) -> httpx.AsyncClient:
    """
    Create configured HTTP client with timeout enforcement.
    
    Args:
        timeout_seconds: Request timeout
        max_retries: Max retry attempts
        **kwargs: Additional httpx.AsyncClient arguments
    
    Returns:
        Configured httpx.AsyncClient
    
    Usage:
        async with create_http_client(timeout_seconds=30) as client:
            response = await client.post(url, json=payload)
    """
    timeout = httpx.Timeout(
        connect=10.0,  # Connection timeout
        read=timeout_seconds,  # Read timeout
        write=10.0,  # Write timeout
        pool=5.0  # Connection pool timeout
    )
    
    transport = httpx.AsyncHTTPTransport(
        retries=max_retries
    )
    
    return httpx.AsyncClient(
        timeout=timeout,
        transport=transport,
        **kwargs
    )


class TimeoutContext:
    """
    Context manager for timeout-aware operations.
    
    Tracks elapsed time and raises timeout if exceeded.
    
    Usage:
        async with TimeoutContext(timeout_seconds=30, provider="groq") as ctx:
            # Perform operation
            result = await some_async_call()
            # Check if timeout approaching
            if ctx.time_remaining() < 5:
                # Abort early
                return partial_result
    """
    
    def __init__(self, timeout_seconds: int, provider: str):
        self.timeout_seconds = timeout_seconds
        self.provider = provider
        self.start_time = None
        self.task = None
    
    async def __aenter__(self):
        import time
        self.start_time = time.perf_counter()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cancel task if timeout
        if self.task and not self.task.done():
            self.task.cancel()
        return False
    
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds"""
        import time
        if self.start_time is None:
            return 0.0
        return time.perf_counter() - self.start_time
    
    def time_remaining(self) -> float:
        """Get remaining time in seconds"""
        return max(0.0, self.timeout_seconds - self.elapsed_seconds())
    
    def is_timeout(self) -> bool:
        """Check if timeout exceeded"""
        return self.elapsed_seconds() >= self.timeout_seconds
    
    def raise_if_timeout(self):
        """Raise timeout error if exceeded"""
        if self.is_timeout():
            raise LLMTimeoutError(
                provider=self.provider,
                timeout_seconds=self.timeout_seconds
            )
