# Coding Sandbox Layer - Isolated Execution Environment

## 1. Purpose

**Why this submodule exists:**

The Coding Sandbox layer is the **security boundary** for untrusted code execution. It:

- Provides isolated execution environment (Docker containers)
- Enforces resource limits at OS level (CPU, memory, processes)
- Prevents host system compromise
- Captures execution output (stdout, stderr, exit code, metrics)
- Supports C++, Java, Python3 runtimes

**Critical responsibility:** This is the **highest-risk security boundary** in the system. One weakness here can compromise the entire infrastructure. Sandbox MUST be paranoid, strict, and hardened.

**Architectural philosophy:**

> **Never trust the code you're running.**
> **Always assume adversarial input.**
> **Fail closed, not open.**

---

## 2. Owned Tables / Entities

**None.** Sandbox layer is stateless. It only executes code and returns results.

---

## 3. Input Contracts

### SandboxExecutionRequest

```python
from pydantic import BaseModel, Field
from typing import Literal

class SandboxExecutionRequest(BaseModel):
    language: Literal["cpp", "java", "python3"]
    source_code: str = Field(max_length=50000)
    input_data: str = Field(default="", max_length=10485760)  # 10MB max input
    time_limit_ms: int = Field(ge=100, le=30000)  # 100ms to 30s
    memory_limit_kb: int = Field(ge=4096, le=1048576)  # 4MB to 1GB
```

---

## 4. Output Contracts

### SandboxExecutionResult

```python
from pydantic import BaseModel

class SandboxExecutionResult(BaseModel):
    stdout: str  # Standard output
    stderr: str  # Standard error
    exit_code: int  # Process exit code (0 = success)
    runtime_ms: int  # Actual execution time
    memory_kb: int  # Peak memory usage
    timed_out: bool  # True if killed due to timeout
    memory_exceeded: bool  # True if killed due to OOM
    compilation_output: str = ""  # For C++/Java compilation errors
```

---

## 5. Acceptance Criteria

### Docker-Based Sandbox (Initial Implementation)

**Container Configuration:**

```bash
docker run \
  --rm \
  --network=none \
  --pids-limit=1 \
  --memory=256m \
  --memory-swap=256m \
  --cpus=1.0 \
  --read-only \
  --tmpfs /tmp:rw,size=100m,mode=1777 \
  --security-opt=no-new-privileges \
  --cap-drop=ALL \
  --user=1000:1000 \
  code-sandbox-python3:latest \
  /sandbox/execute.sh
```

**Explanation:**

- `--rm`: Auto-remove container after execution
- `--network=none`: No network access
- `--pids-limit=1`: Prevent fork bombs
- `--memory=256m`: Memory limit
- `--memory-swap=256m`: Disable swap (prevent memory limit bypass)
- `--cpus=1.0`: CPU limit (1 core max)
- `--read-only`: Filesystem read-only except tmpfs
- `--tmpfs /tmp`: Writable temp directory for compilation
- `--security-opt=no-new-privileges`: Prevent privilege escalation
- `--cap-drop=ALL`: Drop all capabilities (no raw sockets, etc.)
- `--user=1000:1000`: Run as non-root

---

### Language-Specific Execution

#### C++ Execution

**Compilation:**

```bash
# Inside container
cd /tmp
echo "$SOURCE_CODE" > solution.cpp

# Compile with timeout
timeout 10s g++ -std=c++17 -O2 -Wall -Wextra \
  -o solution solution.cpp 2>&1

# Check compilation success
if [ $? -ne 0 ]; then
    echo "COMPILATION_ERROR"
    exit 1
fi
```

**Execution:**

```bash
# Run with input, timeout, and resource monitoring
echo "$INPUT_DATA" | timeout ${TIME_LIMIT_SECONDS}s \
  /usr/bin/time -v ./solution 2>&1

# Capture:
# - stdout (program output)
# - stderr (runtime errors)
# - /usr/bin/time -v output (memory usage, wall time)
# - exit code
```

---

#### Java Execution

**Compilation:**

```bash
cd /tmp
echo "$SOURCE_CODE" > Solution.java

# Compile
timeout 10s javac Solution.java 2>&1

if [ $? -ne 0 ]; then
    echo "COMPILATION_ERROR"
    exit 1
fi
```

**Execution:**

```bash
# Run with memory limit
echo "$INPUT_DATA" | timeout ${TIME_LIMIT_SECONDS}s \
  java -Xmx${MEMORY_LIMIT_MB}m -Xms${MEMORY_LIMIT_MB}m \
  -XX:+UseSerialGC \
  Solution 2>&1
```

**Why these JVM flags?**

- `-Xmx`: Max heap size (enforce memory limit)
- `-Xms`: Initial heap size (same as max for predictability)
- `-XX:+UseSerialGC`: Minimize GC overhead

---

#### Python3 Execution

**No compilation needed.**

**Execution:**

```bash
cd /tmp
echo "$SOURCE_CODE" > solution.py

# Run with input
echo "$INPUT_DATA" | timeout ${TIME_LIMIT_SECONDS}s \
  /usr/bin/time -v python3 solution.py 2>&1
```

**Python-specific resource limits:**

- Use `resource.setrlimit(resource.RLIMIT_AS, memory_limit)` within container
- Prevents memory exhaustion

---

### Security: Seccomp Profile

**Purpose:** Block dangerous syscalls that could be used for escape or DoS.

**Blocked syscalls:**

- `mount`, `umount` - Prevent filesystem manipulation
- `reboot`, `shutdown` - Prevent host restart
- `ptrace` - Prevent debugging other processes
- `kill` (except self) - Prevent killing other containers
- `setuid`, `setgid` - Prevent privilege escalation
- `socket`, `bind`, `connect` - Prevent network access (redundant with `--network=none`)
- `execve` (selectively) - Prevent arbitrary command execution

**Seccomp profile JSON:**

```json
{
  "defaultAction": "SCMP_ACT_ALLOW",
  "syscalls": [
    {
      "names": [
        "mount",
        "umount",
        "umount2",
        "reboot",
        "shutdown",
        "ptrace",
        "setuid",
        "setgid",
        "setreuid",
        "setregid",
        "unshare",
        "clone",
        "keyctl",
        "add_key",
        "request_key"
      ],
      "action": "SCMP_ACT_ERRNO"
    }
  ]
}
```

**Usage:**

```bash
docker run --security-opt seccomp=/path/to/seccomp.json ...
```

---

### Execution Monitoring

**Capture metrics:**

1. **Runtime (ms):**
   - Use `/usr/bin/time -v` to capture wall clock time
   - Parse output: `Elapsed (wall clock) time (h:mm:ss or m:ss): 0:01.23` → 1230 ms

2. **Memory (KB):**
   - Parse `/usr/bin/time -v` output: `Maximum resident set size (kbytes): 12000` → 12000 KB

3. **Exit Code:**
   - Capture process exit code
   - 0 = success
   - Non-zero = error

4. **Timeout Detection:**
   - If `timeout` command kills process, exit code = 124
   - Set `timed_out = True`

5. **OOM Detection:**
   - If Docker OOM killer terminates process, exit code = 137
   - Set `memory_exceeded = True`

---

### Output Sanitization

**Must sanitize:**

- Internal paths: `/tmp/sandbox/solution.cpp` → `solution.cpp`
- User info: Container UID/GID
- System info: Kernel version, host details

**Example:**

```python
def sanitize_output(output: str) -> str:
    # Remove absolute paths
    output = output.replace("/tmp/sandbox/", "")
    output = output.replace("/tmp/", "")

    # Remove container-specific info
    output = re.sub(r"container_id=[a-f0-9]+", "container_id=<hidden>", output)

    return output
```

---

## 6. Invariants & Constraints

### Must Hold

1. **Network Isolation:** Sandbox NEVER has network access
2. **Filesystem Isolation:** Sandbox CANNOT access host filesystem
3. **Process Isolation:** Sandbox CANNOT affect other containers or host processes
4. **Resource Limits:** All executions respect time/memory/process limits
5. **Non-Root Execution:** Sandbox ALWAYS runs as non-root user
6. **Stateless Execution:** Each execution is independent (no persistent state)

### Forbidden

- MUST NOT run as root (UID 0)
- MUST NOT have network access
- MUST NOT mount host directories (except read-only code/data)
- MUST NOT allow privilege escalation
- MUST NOT leave orphaned processes
- MUST NOT exceed resource limits without being killed
- MUST NOT expose host system information

---

## 7. Dependent Modules

### Upstream (Callers)

1. **Execution Module:** Sends execution requests, receives results

### Downstream (Dependencies)

1. **Docker Engine:** Container runtime
2. **Host OS:** Enforces cgroups, namespaces, seccomp

---

## 8. Security Hardening Checklist

### Container Hardening

- [ ] Run as non-root user (UID 1000)
- [ ] Network disabled (`--network=none`)
- [ ] Read-only root filesystem (`--read-only`)
- [ ] No new privileges (`--security-opt=no-new-privileges`)
- [ ] Drop all capabilities (`--cap-drop=ALL`)
- [ ] Process limit (`--pids-limit=1`)
- [ ] Memory limit (`--memory`, `--memory-swap`)
- [ ] CPU limit (`--cpus`)
- [ ] Seccomp profile enabled
- [ ] Auto-remove on exit (`--rm`)

### Runtime Hardening

- [ ] Compilation timeout enforced (10s)
- [ ] Execution timeout enforced (configurable)
- [ ] Memory limit enforced (configurable)
- [ ] Kill process tree on timeout (no orphans)
- [ ] Input size validated (<10MB)
- [ ] Output truncated if excessively large (>1MB)

### Image Hardening

- [ ] Minimal base image (Alpine Linux or distroless)
- [ ] Only required packages installed (gcc, java, python3)
- [ ] No unnecessary tools (curl, wget, netcat)
- [ ] Image scanned for vulnerabilities (Trivy, Snyk)
- [ ] Regular image updates (security patches)

---

## 9. Edge Cases to Handle

### 1. Infinite Loop

**Code:**

```python
while True:
    pass
```

**Handling:**

- `timeout` command kills process after time_limit_ms
- exit_code = 124
- `timed_out = True`
- stdout = "" (no output before timeout)

---

### 2. Memory Bomb

**Code:**

```python
arr = [0] * (10 ** 10)  # Allocate 10GB
```

**Handling:**

- Docker memory limit enforced
- OOM killer terminates process
- exit_code = 137
- `memory_exceeded = True`

---

### 3. Fork Bomb

**Code:**

```python
import os
while True:
    os.fork()
```

**Handling:**

- `--pids-limit=1` prevents additional processes
- fork() fails with "Resource temporarily unavailable"
- Process may crash
- Sandbox reports error

---

### 4. File System Abuse

**Code:**

```python
with open('/etc/passwd', 'r') as f:
    print(f.read())
```

**Handling:**

- Read-only root filesystem
- Seccomp blocks dangerous syscalls
- open() fails with "Permission denied"
- Process may crash or print error

---

### 5. Network Access Attempt

**Code:**

```python
import requests
print(requests.get('https://google.com').text)
```

**Handling:**

- `--network=none` disables network
- `requests.get()` fails with "Network is unreachable"
- Process may crash or print error

---

### 6. Excessive Output

**Code:**

```python
for i in range(10**9):
    print("A" * 10000)
```

**Handling:**

- Truncate stdout after 1MB
- Append "... (output truncated)"
- Prevent memory exhaustion from storing output

---

### 7. Binary Output

**Code:**

```python
import sys
sys.stdout.buffer.write(b'\x00\x01\x02')
```

**Handling:**

- Capture raw bytes
- Convert to string (UTF-8, errors='replace')
- May contain replacement characters (� for invalid bytes)

---

### 8. Compilation Timeout (C++)

**Code:**

```cpp
#include <iostream>
template<int N>
struct Fib {
    static const int value = Fib<N-1>::value + Fib<N-2>::value;
};
// ... instantiate Fib<1000>
```

**Handling:**

- Compilation exceeds 10s timeout
- g++ process killed
- Compilation error reported

---

## 10. Container Image Specifications

### Dockerfile: Python3

```dockerfile
FROM python:3.11-alpine

# Create non-root user
RUN adduser -D -u 1000 sandbox

# Install time utility for metrics
RUN apk add --no-cache time

# Set working directory
WORKDIR /tmp

# Switch to non-root user
USER sandbox

# Default command
CMD ["/bin/sh"]
```

---

### Dockerfile: C++

```dockerfile
FROM gcc:12-alpine

RUN adduser -D -u 1000 sandbox
RUN apk add --no-cache time

WORKDIR /tmp
USER sandbox

CMD ["/bin/sh"]
```

---

### Dockerfile: Java

```dockerfile
FROM openjdk:17-alpine

RUN adduser -D -u 1000 sandbox
RUN apk add --no-cache time

WORKDIR /tmp
USER sandbox

CMD ["/bin/sh"]
```

---

## 11. Execution Script (Inside Container)

### `/sandbox/execute.sh`

```bash
#!/bin/sh
set -e

# Read environment variables
LANGUAGE=${LANGUAGE:-python3}
TIME_LIMIT_SECONDS=${TIME_LIMIT_SECONDS:-2}
MEMORY_LIMIT_MB=${MEMORY_LIMIT_MB:-256}

cd /tmp

# Save source code to file
echo "$SOURCE_CODE" > /tmp/solution.$EXTENSION

# Compilation (if needed)
if [ "$LANGUAGE" = "cpp" ]; then
    timeout 10 g++ -std=c++17 -O2 -Wall -o /tmp/solution /tmp/solution.cpp 2>&1 || exit 1
elif [ "$LANGUAGE" = "java" ]; then
    timeout 10 javac /tmp/solution.java 2>&1 || exit 1
fi

# Execution
if [ "$LANGUAGE" = "cpp" ]; then
    echo "$INPUT_DATA" | timeout $TIME_LIMIT_SECONDS /usr/bin/time -v /tmp/solution 2>&1
elif [ "$LANGUAGE" = "java" ]; then
    echo "$INPUT_DATA" | timeout $TIME_LIMIT_SECONDS java -Xmx${MEMORY_LIMIT_MB}m Solution 2>&1
elif [ "$LANGUAGE" = "python3" ]; then
    echo "$INPUT_DATA" | timeout $TIME_LIMIT_SECONDS /usr/bin/time -v python3 /tmp/solution.py 2>&1
fi

# Exit with execution exit code
exit $?
```

---

## 12. Configuration

### Environment Variables

```bash
# Docker
DOCKER_HOST=unix:///var/run/docker.sock
DOCKER_IMAGE_PYTHON=code-sandbox-python3:latest
DOCKER_IMAGE_CPP=code-sandbox-cpp:latest
DOCKER_IMAGE_JAVA=code-sandbox-java:latest

# Resource Limits
DEFAULT_TIME_LIMIT_MS=2000
DEFAULT_MEMORY_LIMIT_KB=262144
MAX_OUTPUT_SIZE_BYTES=1048576  # 1MB
MAX_INPUT_SIZE_BYTES=10485760  # 10MB

# Security
SECCOMP_PROFILE_PATH=/etc/docker/seccomp-sandbox.json
SANDBOX_USER_UID=1000
SANDBOX_USER_GID=1000
```

---

## 13. Testing Requirements

**Must test:**

### Security Tests

1. **Infinite Loop:** Verify timeout enforced
2. **Memory Bomb:** Verify OOM killer terminates process
3. **Fork Bomb:** Verify process limit prevents fork
4. **File Read Attempt:** Verify read-only filesystem blocks access
5. **Network Request:** Verify network disabled
6. **Privilege Escalation:** Verify blocked by seccomp/no-new-privileges
7. **Syscall Abuse:** Verify dangerous syscalls blocked by seccomp

### Functional Tests

1. **C++ Hello World:** Verify compilation and execution
2. **Java Hello World:** Verify compilation and execution
3. **Python Print:** Verify direct execution
4. **Large Input (10MB):** Verify handled correctly
5. **Large Output (10MB):** Verify truncation
6. **Binary Output:** Verify UTF-8 conversion
7. **Runtime Error:** Verify stderr captured
8. **Compilation Error:** Verify compiler output captured

---

## 14. Future Enhancements

1. **Firecracker MicroVMs:**
   - Faster startup (<1s vs Docker's ~5s)
   - Stronger isolation (hardware virtualization)

2. **gVisor:**
   - User-space kernel for additional isolation
   - Compatible with Docker

3. **Kata Containers:**
   - Lightweight VMs with OCI interface
   - Better isolation than containers

4. **Language Support Expansion:**
   - JavaScript (Node.js)
   - Go
   - Rust
   - C#

5. **GPU Support:**
   - For ML/AI problems
   - CUDA-enabled containers

---

**End of Coding Sandbox Layer Requirements**

---

## Architectural Intent

The sandbox is:

- The **security boundary** protecting infrastructure from untrusted code
- **Paranoid, strict, and hardened**
- **Stateless and isolated**

Every line of code here is a defense against adversarial input.

**Never trust. Always verify. Fail closed.**
