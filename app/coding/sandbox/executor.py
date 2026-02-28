"""
Sandbox Executor — Main Orchestration Service for Code Execution

This is the primary public interface of the sandbox submodule.
The execution layer calls SandboxExecutor.execute() with a
SandboxExecutionRequest and receives a SandboxExecutionResult.

Orchestration flow:
1. Validate request (language, code size, input size)
2. Resolve Docker image from config
3. Build execution script for the language
4. Configure Docker container with security hardening
5. Execute container
6. Parse output (extract metrics, separate stdout/time output)
7. Sanitize output (remove internal paths, system info)
8. Return structured result

Security invariants enforced:
- Network isolation (always)
- Filesystem isolation (always)
- Resource limits (always)
- Non-root execution (always)
- Stateless execution (always)

References:
- REQUIREMENTS.md (all sections)
- SRS FR-7.3: Isolated execution
- SRS NR-5: No untrusted code outside sandbox
- SRS FM-3: Timeout termination
- SRS NFR-3: Initialization within 2s, execution within 5s
"""

import logging
from time import time
from typing import Optional

from app.config.constants import SUPPORTED_LANGUAGES
from app.config.settings import SandboxSettings
from app.shared.errors.exceptions import SandboxExecutionError, SandboxTimeoutError
from app.shared.observability.logging import get_context_logger, ContextLogger
from app.shared.observability.metrics import metrics, track_latency

from app.coding.sandbox.contracts import SandboxExecutionRequest, SandboxExecutionResult
from app.coding.sandbox.docker_runner import (
    DockerRunConfig,
    DockerRunResult,
    get_docker_image,
    build_execution_script,
    run_container,
    SANDBOX_UID,
    SANDBOX_GID,
    LANGUAGE_EXTENSIONS,
)
from app.coding.sandbox.output_parser import (
    parse_execution_output,
    EXIT_CODE_TIMEOUT,
    EXIT_CODE_OOM,
)
from app.coding.sandbox.sanitizer import sanitize_and_truncate


# Safety margin for the hard timeout beyond the requested time limit
# This accounts for container startup, compilation, and cleanup
HARD_TIMEOUT_MARGIN_SECONDS: int = 30

# Compilation overhead (10s compile timeout + margin)
COMPILATION_OVERHEAD_SECONDS: int = 15


class SandboxExecutor:
    """
    Orchestrates isolated code execution in Docker containers.

    This is the ONLY public entry point for sandbox execution.
    It is stateless and thread-safe (no mutable instance state).

    The executor is injected with SandboxSettings via constructor,
    following the repository's Protocol-based DI pattern.

    Usage:
        executor = SandboxExecutor(sandbox_settings)
        result = executor.execute(request)
    """

    def __init__(self, sandbox_settings: SandboxSettings) -> None:
        """
        Initialize SandboxExecutor.

        Args:
            sandbox_settings: Sandbox configuration from app.config.settings.
                              Provides Docker image names, default resource limits,
                              security settings.
        """
        self._settings = sandbox_settings
        self._base_logger = logging.getLogger("app.coding.sandbox")

    def execute(self, request: SandboxExecutionRequest) -> SandboxExecutionResult:
        """
        Execute code in an isolated Docker sandbox.

        This is the primary public method. It:
        1. Validates the request
        2. Builds Docker configuration
        3. Runs the container
        4. Parses and sanitizes output
        5. Returns structured results

        The method is synchronous and blocking. The execution layer
        should call this from an appropriate thread/executor.

        Args:
            request: Validated SandboxExecutionRequest from the execution layer

        Returns:
            SandboxExecutionResult with stdout, stderr, metrics, and status flags

        Raises:
            SandboxExecutionError: If the sandbox infrastructure fails
                (NOT raised for code errors — those are returned in the result)
            SandboxTimeoutError: If the hard timeout is exceeded
                (in-container timeouts are returned in the result, not raised)
        """
        logger = get_context_logger()
        start_time = time()

        logger.info(
            "Sandbox execution started",
            event_type="sandbox_execution_started",
            metadata={
                "language": request.language,
                "code_length": len(request.source_code),
                "input_length": len(request.input_data),
                "time_limit_ms": request.time_limit_ms,
                "memory_limit_kb": request.memory_limit_kb,
            }
        )

        try:
            # Step 1: Resolve Docker image
            image = get_docker_image(request.language, self._settings)

            # Step 2: Compute resource limits
            memory_limit_mb = request.memory_limit_kb // 1024
            time_limit_seconds = request.time_limit_ms / 1000.0

            # Step 3: Build execution script
            script = build_execution_script(
                language=request.language,
                time_limit_seconds=time_limit_seconds,
                memory_limit_mb=memory_limit_mb,
            )

            # Step 4: Build Docker configuration
            docker_config = DockerRunConfig(
                image=image,
                memory_limit_mb=memory_limit_mb,
                time_limit_seconds=time_limit_seconds,
                pids_limit=self._settings.sandbox_process_limit,
                seccomp_profile=self._settings.sandbox_seccomp_profile,
            )

            # Step 5: Build environment variables
            env_vars = {
                "SOURCE_CODE": request.source_code,
                "INPUT_DATA": request.input_data,
                "LANGUAGE": request.language,
            }

            # Step 6: Calculate hard timeout
            # In-container timeout (time limit) + compilation overhead + safety margin
            has_compilation = request.language in ("cpp", "java")
            compilation_extra = COMPILATION_OVERHEAD_SECONDS if has_compilation else 0
            hard_timeout = time_limit_seconds + compilation_extra + HARD_TIMEOUT_MARGIN_SECONDS

            # Step 7: Execute container with metrics tracking
            with track_latency(metrics.sandbox_execution_duration_seconds):
                docker_result = run_container(
                    config=docker_config,
                    env_vars=env_vars,
                    script=script,
                    overall_timeout_seconds=hard_timeout,
                )

            # Step 8: Handle hard timeout (infrastructure failure)
            if docker_result.timed_out:
                elapsed_ms = int((time() - start_time) * 1000)
                metrics.sandbox_timeout_total.inc()

                logger.warning(
                    "Sandbox hard timeout exceeded",
                    event_type="sandbox_hard_timeout",
                    latency_ms=elapsed_ms,
                    metadata={
                        "language": request.language,
                        "hard_timeout_seconds": hard_timeout,
                    }
                )

                return SandboxExecutionResult(
                    stdout="",
                    stderr="Execution timed out",
                    exit_code=EXIT_CODE_TIMEOUT,
                    runtime_ms=request.time_limit_ms,
                    memory_kb=0,
                    timed_out=True,
                    memory_exceeded=False,
                    compilation_output="",
                )

            # Step 9: Process output
            result = self._process_docker_result(
                docker_result=docker_result,
                request=request,
                logger=logger,
            )

            # Step 10: Log completion
            elapsed_ms = int((time() - start_time) * 1000)
            logger.info(
                "Sandbox execution completed",
                event_type="sandbox_execution_completed",
                latency_ms=elapsed_ms,
                metadata={
                    "language": request.language,
                    "exit_code": result.exit_code,
                    "runtime_ms": result.runtime_ms,
                    "memory_kb": result.memory_kb,
                    "timed_out": result.timed_out,
                    "memory_exceeded": result.memory_exceeded,
                }
            )

            return result

        except (SandboxExecutionError, SandboxTimeoutError):
            # Re-raise sandbox-specific errors
            raise

        except Exception as e:
            elapsed_ms = int((time() - start_time) * 1000)
            metrics.sandbox_error_total.labels(error_type="infrastructure").inc()

            logger.error(
                "Sandbox infrastructure error",
                event_type="sandbox_infrastructure_error",
                latency_ms=elapsed_ms,
                metadata={"error": str(e), "language": request.language},
                exc_info=True,
            )

            raise SandboxExecutionError(
                message=f"Sandbox execution failed: {str(e)}",
                metadata={"language": request.language},
            ) from e

    def _process_docker_result(
        self,
        docker_result: DockerRunResult,
        request: SandboxExecutionRequest,
        logger: ContextLogger,
    ) -> SandboxExecutionResult:
        """
        Process raw Docker output into a structured SandboxExecutionResult.

        Handles:
        - Compilation error detection
        - Output parsing (metrics extraction)
        - Output sanitization
        - Timeout/OOM classification

        Args:
            docker_result: Raw Docker container result
            request: Original execution request (for limits reference)
            logger: Context logger for event tracking

        Returns:
            SandboxExecutionResult with processed data
        """
        # Check for compilation errors
        # Compilation errors produce exit code != 0 and output starts with COMPILATION_ERROR
        combined_output = docker_result.stdout or ""
        stderr_output = docker_result.stderr or ""

        has_compilation = request.language in ("cpp", "java")

        if has_compilation and self._is_compilation_error(combined_output, docker_result.exit_code):
            compilation_output = self._extract_compilation_output(combined_output)

            logger.info(
                "Compilation error detected",
                event_type="sandbox_compilation_error",
                metadata={"language": request.language}
            )

            return SandboxExecutionResult(
                stdout="",
                stderr="",
                exit_code=docker_result.exit_code,
                runtime_ms=0,
                memory_kb=0,
                timed_out=False,
                memory_exceeded=False,
                compilation_output=sanitize_and_truncate(compilation_output),
            )

        # Parse execution output (separates program output from /usr/bin/time metrics)
        separated, parsed_metrics = parse_execution_output(
            combined_output=combined_output,
            container_exit_code=docker_result.exit_code,
        )

        # Sanitize program output
        sanitized_stdout = sanitize_and_truncate(separated.program_stdout)
        sanitized_stderr = sanitize_and_truncate(
            stderr_output if stderr_output else separated.program_stderr
        )

        # Classify timeout/OOM
        timed_out = parsed_metrics.timed_out
        memory_exceeded = parsed_metrics.memory_exceeded

        # Update metrics counters
        if timed_out:
            metrics.sandbox_timeout_total.inc()
        if memory_exceeded:
            metrics.sandbox_error_total.labels(error_type="oom").inc()

        # Clamp runtime to time limit if timed out
        runtime_ms = parsed_metrics.runtime_ms
        if timed_out:
            runtime_ms = request.time_limit_ms

        # Clamp memory to limit if OOM
        memory_kb = parsed_metrics.memory_kb
        if memory_exceeded:
            memory_kb = request.memory_limit_kb

        return SandboxExecutionResult(
            stdout=sanitized_stdout,
            stderr=sanitized_stderr,
            exit_code=parsed_metrics.exit_code,
            runtime_ms=runtime_ms,
            memory_kb=memory_kb,
            timed_out=timed_out,
            memory_exceeded=memory_exceeded,
            compilation_output="",
        )

    @staticmethod
    def _is_compilation_error(output: str, exit_code: int) -> bool:
        """
        Detect if the output indicates a compilation error.

        Compilation errors are identified by:
        - Non-zero exit code
        - Output starts with 'COMPILATION_ERROR' marker

        The execution scripts in docker_runner.py emit this marker
        when compilation fails.

        Args:
            output: Combined output from the container
            exit_code: Container exit code

        Returns:
            True if this is a compilation error
        """
        if exit_code == 0:
            return False

        return output.strip().startswith("COMPILATION_ERROR")

    @staticmethod
    def _extract_compilation_output(output: str) -> str:
        """
        Extract the actual compiler error message from compilation output.

        Removes the 'COMPILATION_ERROR' marker prefix that our
        execution scripts prepend.

        Args:
            output: Raw output containing COMPILATION_ERROR marker

        Returns:
            Compiler error message without the marker
        """
        lines = output.strip().split("\n")

        # Skip the COMPILATION_ERROR marker line
        if lines and lines[0].strip() == "COMPILATION_ERROR":
            return "\n".join(lines[1:]).strip()

        return output.strip()
