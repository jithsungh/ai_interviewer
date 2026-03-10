#!/bin/bash
# Build all sandbox Docker images for code execution
# Usage: ./build_sandbox_images.sh
#
# Images built:
#   code-sandbox-python:latest   — Python 3.12
#   code-sandbox-cpp:latest      — GCC 13 (C++17)
#   code-sandbox-java:latest     — JDK 17 (Eclipse Temurin)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SANDBOX_DIR="${SCRIPT_DIR}/sandbox"

echo "=== Building sandbox Docker images ==="

echo ""
echo "[1/3] Building code-sandbox-python:latest ..."
docker build -t code-sandbox-python:latest "${SANDBOX_DIR}/python"

echo ""
echo "[2/3] Building code-sandbox-cpp:latest ..."
docker build -t code-sandbox-cpp:latest "${SANDBOX_DIR}/cpp"

echo ""
echo "[3/3] Building code-sandbox-java:latest ..."
docker build -t code-sandbox-java:latest "${SANDBOX_DIR}/java"

echo ""
echo "=== All sandbox images built successfully ==="
echo ""
docker images | grep code-sandbox
