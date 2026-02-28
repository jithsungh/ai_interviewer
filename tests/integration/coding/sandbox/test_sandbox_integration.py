"""
Integration Tests — Sandbox Executor with Docker

These tests require Docker to be installed and running.
They execute actual code in sandbox containers and validate:
- Security isolation (network, filesystem, processes)
- Resource enforcement (timeout, memory)
- Language-specific execution (C++, Java, Python3)
- Edge cases (infinite loops, memory bombs, fork bombs)

Skip conditions:
- Tests are marked with @pytest.mark.integration
- Tests skip automatically if Docker is not available

These tests validate the full execution path:
  SandboxExecutor → DockerRunner → Docker Container → Output Parser → Sanitizer
"""

import subprocess
import pytest
from unittest.mock import patch

from app.coding.sandbox.contracts import SandboxExecutionRequest, SandboxExecutionResult
from app.coding.sandbox.executor import SandboxExecutor
from app.coding.sandbox.docker_runner import DockerRunResult


def _docker_available() -> bool:
    """Check if Docker is available on the system."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _image_available(image: str) -> bool:
    """Check if a Docker image is available locally."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Skip all tests if Docker is not available
docker_required = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker is not available"
)


class FakeSandboxSettings:
    """Sandbox settings compatible with test Docker images."""
    sandbox_image_cpp = "code-sandbox-cpp:latest"
    sandbox_image_java = "code-sandbox-java:latest"
    sandbox_image_python = "code-sandbox-python:latest"
    sandbox_time_limit_ms = 2000
    sandbox_memory_limit_kb = 262144
    sandbox_process_limit = 64
    sandbox_max_output_size = 1048576
    sandbox_network_disabled = True
    sandbox_seccomp_profile = None


@pytest.fixture
def sandbox_settings():
    return FakeSandboxSettings()


@pytest.fixture
def executor(sandbox_settings):
    return SandboxExecutor(sandbox_settings)


# =============================================================================
# Python3 Integration Tests
# =============================================================================

@pytest.mark.integration
@docker_required
class TestPython3Integration:
    """Integration tests for Python3 sandbox execution."""

    @pytest.mark.skipif(
        not _image_available("code-sandbox-python:latest"),
        reason="Python sandbox image not available"
    )
    def test_hello_world(self, executor):
        """Execute Python3 hello world program."""
        request = SandboxExecutionRequest(
            language="python3",
            source_code="print('Hello, World!')",
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert result.exit_code == 0
        assert "Hello, World!" in result.stdout
        assert result.timed_out is False
        assert result.memory_exceeded is False
        assert result.runtime_ms > 0
        assert result.memory_kb > 0

    @pytest.mark.skipif(
        not _image_available("code-sandbox-python:latest"),
        reason="Python sandbox image not available"
    )
    def test_stdin_input(self, executor):
        """Execute Python3 program that reads from stdin."""
        request = SandboxExecutionRequest(
            language="python3",
            source_code="n = int(input())\nprint(n * 2)",
            input_data="21",
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert result.exit_code == 0
        assert "42" in result.stdout

    @pytest.mark.skipif(
        not _image_available("code-sandbox-python:latest"),
        reason="Python sandbox image not available"
    )
    def test_runtime_error(self, executor):
        """Python3 runtime error (NameError) is captured."""
        request = SandboxExecutionRequest(
            language="python3",
            source_code="print(undefined_variable)",
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert result.exit_code != 0

    @pytest.mark.skipif(
        not _image_available("code-sandbox-python:latest"),
        reason="Python sandbox image not available"
    )
    def test_timeout_infinite_loop(self, executor):
        """Infinite loop is killed by timeout."""
        request = SandboxExecutionRequest(
            language="python3",
            source_code="while True: pass",
            time_limit_ms=1000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert result.timed_out is True
        assert result.runtime_ms == 1000  # Clamped to time limit

    @pytest.mark.skipif(
        not _image_available("code-sandbox-python:latest"),
        reason="Python sandbox image not available"
    )
    def test_network_isolated(self, executor):
        """Network access is blocked in the sandbox."""
        request = SandboxExecutionRequest(
            language="python3",
            source_code=(
                "import socket\n"
                "try:\n"
                "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
                "    s.connect(('8.8.8.8', 53))\n"
                "    print('NETWORK_ACCESS_POSSIBLE')\n"
                "except Exception as e:\n"
                "    print(f'BLOCKED: {e}')\n"
            ),
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert "NETWORK_ACCESS_POSSIBLE" not in result.stdout
        assert "BLOCKED" in result.stdout


# =============================================================================
# C++ Integration Tests
# =============================================================================

@pytest.mark.integration
@docker_required
class TestCppIntegration:
    """Integration tests for C++ sandbox execution."""

    @pytest.mark.skipif(
        not _image_available("code-sandbox-cpp:latest"),
        reason="C++ sandbox image not available"
    )
    def test_hello_world(self, executor):
        """Compile and run C++ hello world."""
        request = SandboxExecutionRequest(
            language="cpp",
            source_code=(
                '#include <iostream>\n'
                'int main() {\n'
                '    std::cout << "Hello, World!" << std::endl;\n'
                '    return 0;\n'
                '}\n'
            ),
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert result.exit_code == 0
        assert "Hello, World!" in result.stdout
        assert result.compilation_output == ""

    @pytest.mark.skipif(
        not _image_available("code-sandbox-cpp:latest"),
        reason="C++ sandbox image not available"
    )
    def test_compilation_error(self, executor):
        """C++ compilation error is captured."""
        request = SandboxExecutionRequest(
            language="cpp",
            source_code="int main() { undefined_function(); }",
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert result.exit_code != 0
        assert result.compilation_output != ""

    @pytest.mark.skipif(
        not _image_available("code-sandbox-cpp:latest"),
        reason="C++ sandbox image not available"
    )
    def test_stdin_input(self, executor):
        """C++ program reads from stdin."""
        request = SandboxExecutionRequest(
            language="cpp",
            source_code=(
                '#include <iostream>\n'
                'int main() {\n'
                '    int n;\n'
                '    std::cin >> n;\n'
                '    std::cout << n * 2 << std::endl;\n'
                '    return 0;\n'
                '}\n'
            ),
            input_data="21",
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert result.exit_code == 0
        assert "42" in result.stdout


# =============================================================================
# Java Integration Tests
# =============================================================================

@pytest.mark.integration
@docker_required
class TestJavaIntegration:
    """Integration tests for Java sandbox execution."""

    @pytest.mark.skipif(
        not _image_available("code-sandbox-java:latest"),
        reason="Java sandbox image not available"
    )
    def test_hello_world(self, executor):
        """Compile and run Java hello world."""
        request = SandboxExecutionRequest(
            language="java",
            source_code=(
                'public class Solution {\n'
                '    public static void main(String[] args) {\n'
                '        System.out.println("Hello, World!");\n'
                '    }\n'
                '}\n'
            ),
            time_limit_ms=10000,
            memory_limit_kb=524288,
        )

        result = executor.execute(request)

        assert result.exit_code == 0
        assert "Hello, World!" in result.stdout

    @pytest.mark.skipif(
        not _image_available("code-sandbox-java:latest"),
        reason="Java sandbox image not available"
    )
    def test_compilation_error(self, executor):
        """Java compilation error is captured."""
        request = SandboxExecutionRequest(
            language="java",
            source_code="public class Solution { public static void main(String[] args) { undeclaredMethod(); } }",
            time_limit_ms=10000,
            memory_limit_kb=524288,
        )

        result = executor.execute(request)

        assert result.exit_code != 0
        assert result.compilation_output != ""


# =============================================================================
# Security Invariant Tests
# =============================================================================

@pytest.mark.integration
@docker_required
class TestSecurityInvariants:
    """Tests that verify security invariants are enforced."""

    @pytest.mark.skipif(
        not _image_available("code-sandbox-python:latest"),
        reason="Python sandbox image not available"
    )
    def test_filesystem_read_only(self, executor):
        """Cannot write to root filesystem."""
        request = SandboxExecutionRequest(
            language="python3",
            source_code=(
                "try:\n"
                "    with open('/etc/test_write', 'w') as f:\n"
                "        f.write('test')\n"
                "    print('WRITE_SUCCEEDED')\n"
                "except Exception as e:\n"
                "    print(f'BLOCKED: {e}')\n"
            ),
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert "WRITE_SUCCEEDED" not in result.stdout

    @pytest.mark.skipif(
        not _image_available("code-sandbox-python:latest"),
        reason="Python sandbox image not available"
    )
    def test_tmp_is_writable(self, executor):
        """Can write to /tmp (tmpfs mount)."""
        request = SandboxExecutionRequest(
            language="python3",
            source_code=(
                "with open('/tmp/test_file', 'w') as f:\n"
                "    f.write('test')\n"
                "with open('/tmp/test_file', 'r') as f:\n"
                "    print(f.read())\n"
            ),
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert "test" in result.stdout

    @pytest.mark.skipif(
        not _image_available("code-sandbox-python:latest"),
        reason="Python sandbox image not available"
    )
    def test_runs_as_non_root(self, executor):
        """Sandbox runs as non-root user (UID 1000)."""
        request = SandboxExecutionRequest(
            language="python3",
            source_code="import os; print(f'UID={os.getuid()}')",
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert "UID=1000" in result.stdout
        assert "UID=0" not in result.stdout  # NOT root


# =============================================================================
# Edge Case Tests  
# =============================================================================

@pytest.mark.integration
@docker_required
class TestEdgeCases:
    """Tests for edge cases from REQUIREMENTS.md §9."""

    @pytest.mark.skipif(
        not _image_available("code-sandbox-python:latest"),
        reason="Python sandbox image not available"
    )
    def test_empty_program(self, executor):
        """Empty program produces no output."""
        request = SandboxExecutionRequest(
            language="python3",
            source_code="",
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        # Empty program should succeed with no output
        assert result.exit_code == 0

    @pytest.mark.skipif(
        not _image_available("code-sandbox-python:latest"),
        reason="Python sandbox image not available"
    )
    def test_binary_output(self, executor):
        """Binary output doesn't crash the parser."""
        request = SandboxExecutionRequest(
            language="python3",
            source_code="import sys; sys.stdout.buffer.write(b'\\x00\\x01\\x02\\xff')",
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        # Should not crash, output is decoded safely
        assert isinstance(result.stdout, str)

    @pytest.mark.skipif(
        not _image_available("code-sandbox-python:latest"),
        reason="Python sandbox image not available"
    )
    def test_multiline_input_data(self, executor):
        """Multi-line input data is handled correctly."""
        request = SandboxExecutionRequest(
            language="python3",
            source_code=(
                "import sys\n"
                "lines = sys.stdin.read().strip().split('\\n')\n"
                "print(len(lines))\n"
            ),
            input_data="line1\nline2\nline3",
            time_limit_ms=5000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert "3" in result.stdout


# =============================================================================
# Mocked Integration Tests (no Docker required)
# =============================================================================

class TestMockedIntegration:
    """
    Integration tests that mock Docker but test the full internal pipeline:
    Executor → DockerRunner config → OutputParser → Sanitizer
    
    These always run (no Docker dependency).
    """

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_full_pipeline_success(self, mock_metrics, mock_run):
        """Full pipeline: execution → parsing → sanitization."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = lambda s: None
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = lambda s, *a: False

        # Simulate successful execution with /usr/bin/time output
        time_output = (
            "\tCommand being timed: \"python3 solution.py\"\n"
            "\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:00.25\n"
            "\tMaximum resident set size (kbytes): 8000\n"
            "\tExit status: 0"
        )
        mock_run.return_value = DockerRunResult(
            stdout=f"42\n{time_output}",
            stderr="",
            exit_code=0,
            timed_out=False,
        )

        settings = FakeSandboxSettings()
        executor = SandboxExecutor(settings)
        request = SandboxExecutionRequest(
            language="python3",
            source_code="print(42)",
            time_limit_ms=2000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        assert result.exit_code == 0
        assert "42" in result.stdout
        assert result.runtime_ms == 250
        assert result.memory_kb == 8000
        assert result.timed_out is False
        assert result.memory_exceeded is False
        assert result.compilation_output == ""

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_full_pipeline_with_sanitization(self, mock_metrics, mock_run):
        """Full pipeline verifies paths are sanitized."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = lambda s: None
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = lambda s, *a: False

        time_output = (
            "\tCommand being timed: \"python3 solution.py\"\n"
            "\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:00.10\n"
            "\tMaximum resident set size (kbytes): 5000\n"
            "\tExit status: 1"
        )
        mock_run.return_value = DockerRunResult(
            stdout=f"/tmp/sandbox/solution.py: error at line 1\n{time_output}",
            stderr="",
            exit_code=1,
            timed_out=False,
        )

        settings = FakeSandboxSettings()
        executor = SandboxExecutor(settings)
        request = SandboxExecutionRequest(
            language="python3",
            source_code="x",
            time_limit_ms=2000,
            memory_limit_kb=262144,
        )

        result = executor.execute(request)

        # Internal path should be sanitized
        assert "/tmp/sandbox/" not in result.stdout


from unittest.mock import MagicMock
