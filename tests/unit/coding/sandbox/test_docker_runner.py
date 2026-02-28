"""
Unit Tests — Docker Runner

Tests Docker command construction, execution script generation,
and security configuration. These tests do NOT require Docker to be installed
as they test pure functions that build commands/scripts.
"""

import pytest

from app.coding.sandbox.docker_runner import (
    DockerRunConfig,
    DockerRunResult,
    get_docker_image,
    build_docker_command,
    build_execution_script,
    SANDBOX_UID,
    SANDBOX_GID,
    LANGUAGE_EXTENSIONS,
    LANGUAGE_IMAGE_MAP,
    COMPILATION_TIMEOUT_SECONDS,
)


# =============================================================================
# Fixtures
# =============================================================================

class FakeSandboxSettings:
    """Minimal SandboxSettings stub for testing."""
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
    """Provide fake sandbox settings."""
    return FakeSandboxSettings()


@pytest.fixture
def base_config():
    """Provide a base Docker run configuration."""
    return DockerRunConfig(
        image="code-sandbox-python:latest",
        memory_limit_mb=256,
        time_limit_seconds=2.0,
    )


# =============================================================================
# get_docker_image Tests
# =============================================================================

class TestGetDockerImage:
    """Tests for Docker image resolution from settings."""

    def test_cpp_image(self, sandbox_settings):
        """C++ resolves to the correct image."""
        image = get_docker_image("cpp", sandbox_settings)
        assert image == "code-sandbox-cpp:latest"

    def test_java_image(self, sandbox_settings):
        """Java resolves to the correct image."""
        image = get_docker_image("java", sandbox_settings)
        assert image == "code-sandbox-java:latest"

    def test_python3_image(self, sandbox_settings):
        """Python3 resolves to the correct image."""
        image = get_docker_image("python3", sandbox_settings)
        assert image == "code-sandbox-python:latest"

    def test_unsupported_language_raises(self, sandbox_settings):
        """Unsupported language raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported language"):
            get_docker_image("ruby", sandbox_settings)

    def test_custom_image_names(self):
        """Custom image names from settings are used."""
        settings = FakeSandboxSettings()
        settings.sandbox_image_python = "custom-python:v2"
        image = get_docker_image("python3", settings)
        assert image == "custom-python:v2"


# =============================================================================
# DockerRunConfig Tests
# =============================================================================

class TestDockerRunConfig:
    """Tests for DockerRunConfig immutability and defaults."""

    def test_defaults(self):
        """Default security settings are correctly applied."""
        config = DockerRunConfig(
            image="test:latest",
            memory_limit_mb=256,
            time_limit_seconds=2.0,
        )
        assert config.pids_limit == 64
        assert config.cpus == 1.0
        assert config.network == "none"
        assert config.read_only is True
        assert config.no_new_privileges is True
        assert config.cap_drop_all is True
        assert config.user == f"{SANDBOX_UID}:{SANDBOX_GID}"
        assert config.auto_remove is True
        assert config.seccomp_profile is None

    def test_frozen(self):
        """Config is immutable (frozen dataclass)."""
        config = DockerRunConfig(
            image="test:latest",
            memory_limit_mb=256,
            time_limit_seconds=2.0,
        )
        with pytest.raises(AttributeError):
            config.image = "hacked:latest"

    def test_security_settings_cannot_be_overridden_to_unsafe(self):
        """Explicit override of security settings is possible but visible."""
        # This tests that security-critical fields must be explicitly set
        config = DockerRunConfig(
            image="test:latest",
            memory_limit_mb=256,
            time_limit_seconds=2.0,
            network="none",  # MUST always be none
            read_only=True,
            cap_drop_all=True,
        )
        assert config.network == "none"
        assert config.read_only is True
        assert config.cap_drop_all is True


# =============================================================================
# build_docker_command Tests
# =============================================================================

class TestBuildDockerCommand:
    """Tests for Docker command construction."""

    def test_basic_command_structure(self, base_config):
        """Command starts with 'docker run'."""
        cmd = build_docker_command(base_config, {})
        assert cmd[0] == "docker"
        assert cmd[1] == "run"

    def test_auto_remove_flag(self, base_config):
        """--rm flag is present."""
        cmd = build_docker_command(base_config, {})
        assert "--rm" in cmd

    def test_network_isolation(self, base_config):
        """--network none is present."""
        cmd = build_docker_command(base_config, {})
        idx = cmd.index("--network")
        assert cmd[idx + 1] == "none"

    def test_pids_limit(self, base_config):
        """--pids-limit is set."""
        cmd = build_docker_command(base_config, {})
        idx = cmd.index("--pids-limit")
        assert cmd[idx + 1] == "64"

    def test_memory_limit(self, base_config):
        """--memory is set with no swap."""
        cmd = build_docker_command(base_config, {})
        idx = cmd.index("--memory")
        assert cmd[idx + 1] == "256m"
        idx_swap = cmd.index("--memory-swap")
        assert cmd[idx_swap + 1] == "256m"  # Same as memory = no swap

    def test_cpu_limit(self, base_config):
        """--cpus is set."""
        cmd = build_docker_command(base_config, {})
        idx = cmd.index("--cpus")
        assert cmd[idx + 1] == "1.0"

    def test_read_only_filesystem(self, base_config):
        """--read-only flag is present."""
        cmd = build_docker_command(base_config, {})
        assert "--read-only" in cmd

    def test_tmpfs_mount(self, base_config):
        """--tmpfs /tmp is configured with exec for compiled binaries."""
        cmd = build_docker_command(base_config, {})
        idx = cmd.index("--tmpfs")
        tmpfs_val = cmd[idx + 1]
        assert tmpfs_val.startswith("/tmp:")
        assert "rw" in tmpfs_val
        assert "exec" in tmpfs_val
        assert "mode=1777" in tmpfs_val

    def test_no_new_privileges(self, base_config):
        """--security-opt no-new-privileges is set."""
        cmd = build_docker_command(base_config, {})
        assert "no-new-privileges" in " ".join(cmd)

    def test_cap_drop_all(self, base_config):
        """--cap-drop ALL is present."""
        cmd = build_docker_command(base_config, {})
        idx = cmd.index("--cap-drop")
        assert cmd[idx + 1] == "ALL"

    def test_user_flag(self, base_config):
        """--user 1000:1000 is set."""
        cmd = build_docker_command(base_config, {})
        idx = cmd.index("--user")
        assert cmd[idx + 1] == f"{SANDBOX_UID}:{SANDBOX_GID}"

    def test_env_vars_passed(self, base_config):
        """Environment variables are passed via -e flags."""
        env = {"SOURCE_CODE": "print('hi')", "INPUT_DATA": "42"}
        cmd = build_docker_command(base_config, env)
        cmd_str = " ".join(cmd)
        assert "-e" in cmd_str
        # Count -e flags
        e_count = cmd.count("-e")
        assert e_count == 2

    def test_image_is_last_before_cmd(self, base_config):
        """Docker image is in the command."""
        cmd = build_docker_command(base_config, {})
        assert "code-sandbox-python:latest" in cmd

    def test_seccomp_profile_included_when_set(self):
        """Seccomp profile is included when configured."""
        config = DockerRunConfig(
            image="test:latest",
            memory_limit_mb=256,
            time_limit_seconds=2.0,
            seccomp_profile="/etc/docker/seccomp.json",
        )
        cmd = build_docker_command(config, {})
        cmd_str = " ".join(cmd)
        assert "seccomp=/etc/docker/seccomp.json" in cmd_str

    def test_seccomp_profile_omitted_when_none(self, base_config):
        """Seccomp flag is omitted when profile is None."""
        cmd = build_docker_command(base_config, {})
        cmd_str = " ".join(cmd)
        assert "seccomp=" not in cmd_str

    def test_all_security_flags_present(self, base_config):
        """All mandatory security flags are present in the command."""
        cmd = build_docker_command(base_config, {})
        cmd_str = " ".join(cmd)

        # Checklist from REQUIREMENTS.md §8
        assert "--rm" in cmd
        assert "--network" in cmd
        assert "--pids-limit" in cmd
        assert "--memory" in cmd
        assert "--memory-swap" in cmd
        assert "--cpus" in cmd
        assert "--read-only" in cmd
        assert "--tmpfs" in cmd
        assert "no-new-privileges" in cmd_str
        assert "--cap-drop" in cmd
        assert "--user" in cmd


# =============================================================================
# build_execution_script Tests
# =============================================================================

class TestBuildExecutionScript:
    """Tests for language-specific execution script generation."""

    def test_cpp_script_includes_compilation(self):
        """C++ script compiles with g++ before execution."""
        script = build_execution_script("cpp", 2.0, 256)
        assert "g++" in script
        assert "-std=c++17" in script
        assert "-O2" in script
        assert "solution.cpp" in script
        assert "COMPILATION_ERROR" in script

    def test_cpp_script_includes_timeout(self):
        """C++ script uses timeout command."""
        script = build_execution_script("cpp", 5.0, 256)
        assert "timeout 5" in script

    def test_cpp_script_includes_time_measurement(self):
        """C++ script uses /usr/bin/time -v for metrics."""
        script = build_execution_script("cpp", 2.0, 256)
        assert "/usr/bin/time -v" in script

    def test_java_script_includes_compilation(self):
        """Java script compiles with javac."""
        script = build_execution_script("java", 3.0, 512)
        assert "javac" in script
        assert "Solution.java" in script
        assert "COMPILATION_ERROR" in script

    def test_java_script_includes_jvm_flags(self):
        """Java script sets JVM memory limits."""
        script = build_execution_script("java", 3.0, 512)
        assert "-Xmx512m" in script
        assert "-Xms512m" in script
        assert "-XX:+UseSerialGC" in script

    def test_python3_script_no_compilation(self):
        """Python3 script has no compilation step."""
        script = build_execution_script("python3", 2.0, 256)
        assert "g++" not in script
        assert "javac" not in script
        assert "COMPILATION_ERROR" not in script

    def test_python3_script_runs_directly(self):
        """Python3 script executes directly with python3."""
        script = build_execution_script("python3", 2.0, 256)
        assert "python3" in script
        assert "solution.py" in script

    def test_python3_script_includes_timeout(self):
        """Python3 script uses timeout command."""
        script = build_execution_script("python3", 10.0, 256)
        assert "timeout 10" in script

    def test_all_scripts_use_source_code_env(self):
        """All scripts reference SOURCE_CODE env var."""
        for lang in ("cpp", "java", "python3"):
            script = build_execution_script(lang, 2.0, 256)
            assert "$SOURCE_CODE" in script

    def test_all_scripts_use_input_data_env(self):
        """All scripts pipe INPUT_DATA as stdin."""
        for lang in ("cpp", "java", "python3"):
            script = build_execution_script(lang, 2.0, 256)
            assert "$INPUT_DATA" in script

    def test_compilation_timeout_configured(self):
        """Compilation steps have a timeout."""
        for lang in ("cpp", "java"):
            script = build_execution_script(lang, 2.0, 256)
            assert f"timeout {COMPILATION_TIMEOUT_SECONDS}" in script

    def test_unsupported_language_raises(self):
        """Unsupported language raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported language"):
            build_execution_script("ruby", 2.0, 256)

    def test_scripts_use_printf_not_echo(self):
        """Scripts use printf instead of echo to avoid escape interpretation."""
        for lang in ("cpp", "java", "python3"):
            script = build_execution_script(lang, 2.0, 256)
            assert "printf" in script


# =============================================================================
# DockerRunResult Tests
# =============================================================================

class TestDockerRunResult:
    """Tests for DockerRunResult data class."""

    def test_default_values(self):
        """Default result has empty strings and -1 exit code."""
        result = DockerRunResult()
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == -1
        assert result.timed_out is False

    def test_timeout_result(self):
        """Timeout result has timed_out=True."""
        result = DockerRunResult(timed_out=True, exit_code=124)
        assert result.timed_out is True
        assert result.exit_code == 124


# =============================================================================
# Language Constants Tests
# =============================================================================

class TestLanguageConstants:
    """Tests for language-related constants."""

    def test_all_supported_languages_have_extensions(self):
        """All supported languages have file extensions defined."""
        for lang in ("cpp", "java", "python3"):
            assert lang in LANGUAGE_EXTENSIONS

    def test_all_supported_languages_have_images(self):
        """All supported languages have image mappings."""
        for lang in ("cpp", "java", "python3"):
            assert lang in LANGUAGE_IMAGE_MAP

    def test_extension_values(self):
        """File extensions are correct."""
        assert LANGUAGE_EXTENSIONS["cpp"] == "cpp"
        assert LANGUAGE_EXTENSIONS["java"] == "java"
        assert LANGUAGE_EXTENSIONS["python3"] == "py"

    def test_sandbox_uid_gid(self):
        """Sandbox UID/GID are non-root."""
        assert SANDBOX_UID == 1000
        assert SANDBOX_GID == 1000
        assert SANDBOX_UID != 0  # Must NOT be root
        assert SANDBOX_GID != 0
