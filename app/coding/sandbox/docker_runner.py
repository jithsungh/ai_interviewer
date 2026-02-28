"""
Docker Runner — Low-Level Docker Container Management

Handles the creation, configuration, and execution of Docker containers
for sandboxed code execution. This is the lowest-level interface to Docker.

All security hardening is applied here:
- Network isolation (--network=none)
- Read-only filesystem (--read-only)
- Resource limits (memory, CPU, PIDs)
- Capability dropping (--cap-drop=ALL)
- Non-root execution (--user=1000:1000)
- No privilege escalation (--security-opt=no-new-privileges)
- Auto-removal (--rm)

References:
- REQUIREMENTS.md §5 (Docker-Based Sandbox)
- REQUIREMENTS.md §6 (Invariants & Constraints)
- REQUIREMENTS.md §8 (Security Hardening Checklist)
- SRS NR-5: No untrusted code outside isolated environments
- SRS FM-3: Timeout termination
"""

import subprocess
import shlex
from dataclasses import dataclass, field
from typing import Optional, Final

from app.config.settings import SandboxSettings


# Sandbox user UID/GID (non-root)
SANDBOX_UID: Final[int] = 1000
SANDBOX_GID: Final[int] = 1000

# Compilation timeout in seconds
COMPILATION_TIMEOUT_SECONDS: Final[int] = 10

# tmpfs size for /tmp inside container
TMPFS_SIZE_MB: Final[int] = 100

# CPU limit (number of cores)
CPU_LIMIT: Final[float] = 1.0

# Language-specific file extensions
LANGUAGE_EXTENSIONS: Final[dict[str, str]] = {
    "cpp": "cpp",
    "java": "java",
    "python3": "py",
}

# Language-specific Docker image setting keys
LANGUAGE_IMAGE_MAP: Final[dict[str, str]] = {
    "cpp": "sandbox_image_cpp",
    "java": "sandbox_image_java",
    "python3": "sandbox_image_python",
}


@dataclass(frozen=True)
class DockerRunConfig:
    """
    Immutable configuration for a Docker sandbox container run.

    All security settings are explicit and non-overridable.
    """
    image: str
    memory_limit_mb: int
    time_limit_seconds: float
    pids_limit: int = 64
    cpus: float = CPU_LIMIT
    network: str = "none"
    read_only: bool = True
    no_new_privileges: bool = True
    cap_drop_all: bool = True
    user: str = f"{SANDBOX_UID}:{SANDBOX_GID}"
    auto_remove: bool = True
    tmpfs_tmp_size_mb: int = TMPFS_SIZE_MB
    seccomp_profile: Optional[str] = None


@dataclass
class DockerRunResult:
    """
    Raw result from a Docker container execution.

    Contains the unprocessed output from the container.
    Processing (parsing, sanitization) happens in higher layers.
    """
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    timed_out: bool = False


def get_docker_image(language: str, sandbox_settings: SandboxSettings) -> str:
    """
    Get the Docker image name for a given language.

    Uses SandboxSettings to resolve image names from configuration.

    Args:
        language: Programming language (cpp, java, python3)
        sandbox_settings: Sandbox configuration

    Returns:
        Docker image name with tag

    Raises:
        ValueError: If language is not supported
    """
    attr_name = LANGUAGE_IMAGE_MAP.get(language)
    if attr_name is None:
        raise ValueError(f"Unsupported language: {language}")

    return getattr(sandbox_settings, attr_name)


def build_docker_command(config: DockerRunConfig, env_vars: dict[str, str]) -> list[str]:
    """
    Build the complete docker run command with all security flags.

    This is a pure function that produces the command as a list of strings.
    It does NOT execute anything.

    Security flags applied:
    - --rm: Auto-remove container
    - --network=none: No network access
    - --pids-limit: Prevent fork bombs
    - --memory/--memory-swap: Memory limit (swap disabled)
    - --cpus: CPU limit
    - --read-only: Read-only root filesystem
    - --tmpfs /tmp: Writable temp directory
    - --security-opt=no-new-privileges: No privilege escalation
    - --cap-drop=ALL: Drop all capabilities
    - --user: Run as non-root

    Args:
        config: Docker run configuration
        env_vars: Environment variables to pass to the container

    Returns:
        List of command strings for subprocess execution
    """
    cmd = ["docker", "run"]

    # Auto-remove
    if config.auto_remove:
        cmd.append("--rm")

    # Network isolation
    cmd.extend(["--network", config.network])

    # Process limit
    cmd.extend(["--pids-limit", str(config.pids_limit)])

    # Memory limits (disable swap to prevent memory limit bypass)
    memory_str = f"{config.memory_limit_mb}m"
    cmd.extend(["--memory", memory_str])
    cmd.extend(["--memory-swap", memory_str])

    # CPU limit
    cmd.extend(["--cpus", str(config.cpus)])

    # Read-only filesystem
    if config.read_only:
        cmd.append("--read-only")

    # Writable tmpfs for /tmp (exec needed for compiled binaries)
    tmpfs_opts = f"rw,exec,size={config.tmpfs_tmp_size_mb}m,mode=1777"
    cmd.extend(["--tmpfs", f"/tmp:{tmpfs_opts}"])

    # Security options
    if config.no_new_privileges:
        cmd.extend(["--security-opt", "no-new-privileges"])

    # Seccomp profile
    if config.seccomp_profile:
        cmd.extend(["--security-opt", f"seccomp={config.seccomp_profile}"])

    # Drop all capabilities
    if config.cap_drop_all:
        cmd.extend(["--cap-drop", "ALL"])

    # Non-root user
    cmd.extend(["--user", config.user])

    # Environment variables
    for key, value in env_vars.items():
        cmd.extend(["-e", f"{key}={value}"])

    # Image
    cmd.append(config.image)

    return cmd


def build_execution_script(
    language: str,
    time_limit_seconds: float,
    memory_limit_mb: int
) -> str:
    """
    Build the shell script that runs inside the container.

    Handles:
    - Writing source code from env var to file
    - Compilation (for C++/Java)
    - Execution with timeout and /usr/bin/time for metrics
    - Input data piping

    The script uses environment variables:
    - SOURCE_CODE: The source code to execute
    - INPUT_DATA: Standard input for the program
    - LANGUAGE: Programming language (cpp, java, python3)

    Args:
        language: Programming language
        time_limit_seconds: Execution timeout in seconds
        memory_limit_mb: Memory limit in MB (for Java JVM flags)

    Returns:
        Shell script string to execute inside the container
    """
    time_limit_int = int(time_limit_seconds)

    if language == "cpp":
        return _build_cpp_script(time_limit_int)
    elif language == "java":
        return _build_java_script(time_limit_int, memory_limit_mb)
    elif language == "python3":
        return _build_python3_script(time_limit_int)
    else:
        raise ValueError(f"Unsupported language: {language}")


def _build_cpp_script(time_limit_seconds: int) -> str:
    """Build execution script for C++."""
    return f"""#!/bin/sh
set -e
cd /tmp

# Write source code
printf '%s' "$SOURCE_CODE" > solution.cpp

# Compile with timeout (10s)
COMP_OUTPUT=$(timeout {COMPILATION_TIMEOUT_SECONDS} g++ -std=c++17 -O2 -Wall -Wextra -o solution solution.cpp 2>&1) || {{
    echo "COMPILATION_ERROR"
    echo "$COMP_OUTPUT"
    exit 1
}}

# Execute with timeout and resource monitoring
printf '%s' "$INPUT_DATA" | timeout {time_limit_seconds} /usr/bin/time -v ./solution 2>&1
exit $?
"""


def _build_java_script(time_limit_seconds: int, memory_limit_mb: int) -> str:
    """Build execution script for Java."""
    return f"""#!/bin/sh
set -e
cd /tmp

# Write source code
printf '%s' "$SOURCE_CODE" > Solution.java

# Compile with timeout (10s)
COMP_OUTPUT=$(timeout {COMPILATION_TIMEOUT_SECONDS} javac Solution.java 2>&1) || {{
    echo "COMPILATION_ERROR"
    echo "$COMP_OUTPUT"
    exit 1
}}

# Execute with JVM memory limits
printf '%s' "$INPUT_DATA" | timeout {time_limit_seconds} /usr/bin/time -v java -Xmx{memory_limit_mb}m -Xms{memory_limit_mb}m -XX:+UseSerialGC Solution 2>&1
exit $?
"""


def _build_python3_script(time_limit_seconds: int) -> str:
    """Build execution script for Python3."""
    return f"""#!/bin/sh
cd /tmp

# Write source code
printf '%s' "$SOURCE_CODE" > solution.py

# Execute with timeout and resource monitoring
printf '%s' "$INPUT_DATA" | timeout {time_limit_seconds} /usr/bin/time -v python3 solution.py 2>&1
exit $?
"""


def run_container(
    config: DockerRunConfig,
    env_vars: dict[str, str],
    script: str,
    overall_timeout_seconds: float
) -> DockerRunResult:
    """
    Execute a Docker container with the given configuration and script.

    This is the only function that actually invokes Docker.
    All security enforcement happens via the DockerRunConfig flags.

    The overall_timeout_seconds is a safety net that kills the docker
    process itself if the container hangs, beyond the in-container timeout.

    Args:
        config: Docker security and resource configuration
        env_vars: Environment variables for the container
        script: Shell script to execute inside the container
        overall_timeout_seconds: Hard timeout for the entire docker run process

    Returns:
        DockerRunResult with raw stdout, stderr, exit code
    """
    cmd = build_docker_command(config, env_vars)

    # Append the shell command to execute the script
    cmd.extend(["/bin/sh", "-c", script])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=overall_timeout_seconds,
            # Do NOT use shell=True — prevents shell injection
        )

        return DockerRunResult(
            stdout=result.stdout.decode("utf-8", errors="replace") if result.stdout else "",
            stderr=result.stderr.decode("utf-8", errors="replace") if result.stderr else "",
            exit_code=result.returncode,
            timed_out=False
        )

    except subprocess.TimeoutExpired:
        return DockerRunResult(
            stdout="",
            stderr="Execution timed out (hard timeout)",
            exit_code=EXIT_CODE_TIMEOUT,
            timed_out=True
        )

    except FileNotFoundError:
        # Docker command not found
        return DockerRunResult(
            stdout="",
            stderr="Docker runtime not available",
            exit_code=-1,
            timed_out=False
        )

    except OSError as e:
        return DockerRunResult(
            stdout="",
            stderr=f"OS error running container: {str(e)}",
            exit_code=-1,
            timed_out=False
        )
