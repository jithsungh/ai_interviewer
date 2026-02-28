# Human Testing Guide — `coding/sandbox`

## Module Overview

The `coding/sandbox` module provides **secure Docker-based code execution** for untrusted user submissions. It is an **internal service** (no REST API endpoints) consumed by the upstream `coding/execution` module.

**Key characteristics:**
- Stateless — no database tables, no migrations
- No API routes — invoked programmatically via `SandboxExecutor.execute()`
- Security boundary — Docker isolation with network disabled, filesystem read-only, capabilities dropped

---

## Prerequisites

### 1. Docker Images

The sandbox requires language-specific Docker images. Build or pull them before testing:

```bash
# Check which images are configured
python -c "from app.config.settings import get_settings; s = get_settings(); print(f'Python3: {s.sandbox.python3_image}\nJava: {s.sandbox.java_image}\nC++: {s.sandbox.cpp_image}')"

# Verify images exist locally
docker images | grep -E "sandbox|compiler"
```

If images are missing, build them from `DockerFiles/` or configure `SandboxSettings` to point to available images.

### 2. Docker Daemon

```bash
# Verify Docker is running and accessible
docker info > /dev/null 2>&1 && echo "Docker OK" || echo "Docker NOT available"

# Verify current user can run containers
docker run --rm hello-world
```

### 3. Seccomp Profile (Optional)

If `SandboxSettings.seccomp_profile_path` is set, verify the file exists:

```bash
ls -la $(python -c "from app.config.settings import get_settings; print(get_settings().sandbox.seccomp_profile_path or 'NOT SET')")
```

---

## Module API

### Public Interface

```python
from app.coding.sandbox import SandboxExecutionRequest, SandboxExecutionResult, SandboxExecutor
```

### `SandboxExecutionRequest`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `language` | `Literal["cpp", "java", "python3"]` | Required | Target language |
| `source_code` | `str` | max 50,000 chars | User's code |
| `input_data` | `str` | max 10,485,760 bytes | stdin data |
| `time_limit_ms` | `int` | 100–30,000 | Execution time limit |
| `memory_limit_kb` | `int` | 4,096–1,048,576 | Memory limit |

### `SandboxExecutionResult`

| Field | Type | Description |
|---|---|---|
| `stdout` | `str` | Program output (sanitized, max 1MB) |
| `stderr` | `str` | Error output (sanitized, max 1MB) |
| `exit_code` | `int` | Process exit code |
| `runtime_ms` | `float \| None` | Wall-clock time in ms |
| `memory_kb` | `int \| None` | Peak RSS in KB |
| `timed_out` | `bool` | Whether execution timed out |
| `memory_exceeded` | `bool` | Whether OOM killed |
| `compilation_output` | `str \| None` | Compiler stderr (cpp/java only) |

### `SandboxExecutor`

```python
executor = SandboxExecutor(sandbox_settings=settings.sandbox)
result = executor.execute(request)
```

- Raises `SandboxExecutionError` for **infrastructure** failures (Docker daemon down, image missing)
- Returns `SandboxExecutionResult` with error info for **code** failures (compilation error, runtime error, timeout, OOM)

---

## Interactive Testing (Python REPL)

### Test 1: Successful Python3 Execution

```python
import sys; sys.path.insert(0, ".")
from app.config.settings import get_settings
from app.coding.sandbox import SandboxExecutionRequest, SandboxExecutor

settings = get_settings()
executor = SandboxExecutor(sandbox_settings=settings.sandbox)

request = SandboxExecutionRequest(
    language="python3",
    source_code="print('Hello, Sandbox!')",
    input_data="",
    time_limit_ms=5000,
    memory_limit_kb=262144,
)
result = executor.execute(request)

assert result.exit_code == 0
assert "Hello, Sandbox!" in result.stdout
assert result.timed_out is False
assert result.memory_exceeded is False
print(f"✓ stdout={result.stdout!r}, runtime={result.runtime_ms}ms, memory={result.memory_kb}KB")
```

### Test 2: Python3 with stdin

```python
request = SandboxExecutionRequest(
    language="python3",
    source_code="n = int(input())\nfor i in range(n):\n    print(i)",
    input_data="5",
    time_limit_ms=5000,
    memory_limit_kb=262144,
)
result = executor.execute(request)

assert result.exit_code == 0
assert result.stdout.strip() == "0\n1\n2\n3\n4"
print(f"✓ stdout={result.stdout!r}")
```

### Test 3: C++ Compilation & Execution

```python
cpp_code = """
#include <iostream>
using namespace std;
int main() {
    int a, b;
    cin >> a >> b;
    cout << a + b << endl;
    return 0;
}
"""
request = SandboxExecutionRequest(
    language="cpp",
    source_code=cpp_code,
    input_data="3 7",
    time_limit_ms=10000,
    memory_limit_kb=262144,
)
result = executor.execute(request)

assert result.exit_code == 0
assert "10" in result.stdout
print(f"✓ stdout={result.stdout!r}, compilation={result.compilation_output!r}")
```

### Test 4: Java Compilation & Execution

```python
java_code = """
import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        System.out.println("Sum=" + (sc.nextInt() + sc.nextInt()));
    }
}
"""
request = SandboxExecutionRequest(
    language="java",
    source_code=java_code,
    input_data="10 20",
    time_limit_ms=15000,
    memory_limit_kb=524288,
)
result = executor.execute(request)

assert result.exit_code == 0
assert "Sum=30" in result.stdout
print(f"✓ stdout={result.stdout!r}")
```

### Test 5: Compilation Error (C++)

```python
request = SandboxExecutionRequest(
    language="cpp",
    source_code="int main() { undefined_func(); }",
    input_data="",
    time_limit_ms=10000,
    memory_limit_kb=262144,
)
result = executor.execute(request)

assert result.exit_code != 0
assert result.compilation_output is not None
assert "error" in result.compilation_output.lower() or "undefined" in result.compilation_output.lower()
print(f"✓ Compilation error detected: {result.compilation_output[:200]}")
```

### Test 6: Timeout Detection

```python
request = SandboxExecutionRequest(
    language="python3",
    source_code="while True: pass",
    input_data="",
    time_limit_ms=2000,  # 2 seconds
    memory_limit_kb=262144,
)
result = executor.execute(request)

assert result.timed_out is True
print(f"✓ Timeout detected: timed_out={result.timed_out}, exit_code={result.exit_code}")
```

### Test 7: Memory Limit Exceeded

```python
request = SandboxExecutionRequest(
    language="python3",
    source_code="x = 'A' * (500 * 1024 * 1024)",  # 500MB
    input_data="",
    time_limit_ms=10000,
    memory_limit_kb=65536,  # 64MB
)
result = executor.execute(request)

assert result.memory_exceeded is True or result.exit_code != 0
print(f"✓ Memory exceeded: memory_exceeded={result.memory_exceeded}, exit_code={result.exit_code}")
```

---

## Security Verification

### Verify Network Isolation

```python
request = SandboxExecutionRequest(
    language="python3",
    source_code="""
import urllib.request
try:
    urllib.request.urlopen('http://169.254.169.254/latest/meta-data/', timeout=2)
    print('SECURITY FAILURE: network accessible')
except Exception as e:
    print(f'PASS: network blocked ({type(e).__name__})')
""",
    input_data="",
    time_limit_ms=10000,
    memory_limit_kb=262144,
)
result = executor.execute(request)
assert "PASS: network blocked" in result.stdout
print(f"✓ Network isolation verified")
```

### Verify Filesystem Read-Only

```python
request = SandboxExecutionRequest(
    language="python3",
    source_code="""
import os
try:
    with open('/tmp/test_write', 'w') as f:
        f.write('test')
    # /tmp may be writable via tmpfs; check /etc instead
    with open('/etc/test_write', 'w') as f:
        f.write('test')
    print('SECURITY FAILURE: /etc writable')
except Exception as e:
    print(f'PASS: filesystem protected ({type(e).__name__})')
""",
    input_data="",
    time_limit_ms=5000,
    memory_limit_kb=262144,
)
result = executor.execute(request)
assert "PASS: filesystem protected" in result.stdout or "Read-only" in result.stderr
print(f"✓ Filesystem isolation verified")
```

### Verify Process Runs as Non-Root

```python
request = SandboxExecutionRequest(
    language="python3",
    source_code="import os; print(f'uid={os.getuid()}, gid={os.getgid()}')",
    input_data="",
    time_limit_ms=5000,
    memory_limit_kb=262144,
)
result = executor.execute(request)
assert "uid=0" not in result.stdout  # Must NOT be root
print(f"✓ Non-root execution verified: {result.stdout.strip()}")
```

### Verify Output Sanitization

```python
from app.coding.sandbox.sanitizer import sanitize_output

dirty = "Error at /home/user/.local/lib/python3.12/site.py line 5\nContainer abc123def456 exited\nKernel 5.15.0-generic"
clean = sanitize_output(dirty)
assert "/home/user" not in clean
assert "abc123def456" not in clean
assert "5.15.0" not in clean
print(f"✓ Sanitization verified:\n  Before: {dirty!r}\n  After:  {clean!r}")
```

---

## Observability Verification

### Check Prometheus Metrics

After running a few executions:

```python
from app.shared.observability.metrics import MetricsRegistry

metrics = MetricsRegistry()

# These should show collected samples after executions
print("Duration histogram:", metrics.sandbox_execution_duration_seconds._metrics)
print("Timeout counter:", metrics.sandbox_timeout_total._value.get())
print("Error counter:", metrics.sandbox_error_total._value.get())
```

### Check Structured Logging

Run with `LOG_LEVEL=DEBUG` to see sandbox log entries:

```bash
LOG_LEVEL=DEBUG python -c "
import sys; sys.path.insert(0, '.')
from app.config.settings import get_settings
from app.coding.sandbox import SandboxExecutionRequest, SandboxExecutor
executor = SandboxExecutor(sandbox_settings=get_settings().sandbox)
result = executor.execute(SandboxExecutionRequest(
    language='python3', source_code='print(42)', input_data='',
    time_limit_ms=5000, memory_limit_kb=262144
))
print(result.stdout)
" 2>&1 | grep -i sandbox
```

Expected log lines:
- `"Sandbox execution starting"` with `language`, `code_size`, `time_limit_ms`
- `"Container execution completed"` with `exit_code`, `timed_out`
- `"Sandbox execution completed"` with `runtime_ms`, `memory_kb`

---

## Unit Tests

```bash
# Run all unit tests (no Docker required)
.venv/bin/python -m pytest tests/unit/coding/sandbox/ -v --tb=short

# Run specific test file
.venv/bin/python -m pytest tests/unit/coding/sandbox/test_executor.py -v

# Run with coverage
.venv/bin/python -m pytest tests/unit/coding/sandbox/ --cov=app.coding.sandbox --cov-report=term-missing
```

**Expected: 147 tests, all passing.**

## Integration Tests

```bash
# Run mocked integration tests (no Docker required)
.venv/bin/python -m pytest tests/integration/coding/sandbox/ -v -k "Mocked"

# Run Docker-dependent tests (requires Docker + images)
.venv/bin/python -m pytest tests/integration/coding/sandbox/ -v -k "Docker" --timeout=120

# Run all integration tests
.venv/bin/python -m pytest tests/integration/coding/sandbox/ -v --timeout=120
```

Docker-dependent tests auto-skip via `@pytest.mark.skipif` when Docker is unavailable.

---

## Schema & Migration

**No schema changes required.** The sandbox module is entirely stateless — it does not read from or write to any database tables.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `SandboxExecutionError: Docker command failed` | Docker daemon not running | `sudo systemctl start docker` |
| `SandboxExecutionError: Docker command failed` | Image not found | Build images from `DockerFiles/` |
| `FileNotFoundError: docker` | Docker not installed | Install Docker Engine |
| Timeout test doesn't trigger `timed_out=True` | `time_limit_ms` too high | Lower to 2000ms for testing |
| Memory test doesn't trigger `memory_exceeded` | `memory_limit_kb` too high | Lower to 65536 (64MB) |
| Output contains system paths | Sanitizer not applied | Check `sanitize_and_truncate()` is called |
| Tests fail with `ModuleNotFoundError` | Wrong Python | Use `.venv/bin/python -m pytest` |
