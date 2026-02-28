"""
Coding Sandbox — Isolated Code Execution Security Boundary

Public interface for the sandbox submodule.
The sandbox is stateless, has no persistence, and no API routes.
It is consumed exclusively by the coding/execution layer.

Key exports:
- SandboxExecutionRequest: Input contract
- SandboxExecutionResult: Output contract
- SandboxExecutor: Main execution service
"""

from app.coding.sandbox.contracts import SandboxExecutionRequest, SandboxExecutionResult
from app.coding.sandbox.executor import SandboxExecutor

__all__ = [
    "SandboxExecutionRequest",
    "SandboxExecutionResult",
    "SandboxExecutor",
]
