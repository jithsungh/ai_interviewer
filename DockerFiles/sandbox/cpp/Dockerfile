# Sandbox image for C++ code execution
# Provides: g++ (C++17), /usr/bin/time, timeout, /bin/sh
# Runs as non-root user 1000:1000

FROM debian:bookworm-slim

# Install g++, GNU time, and coreutils (timeout)
RUN apt-get update && \
    apt-get install -y --no-install-recommends g++ time coreutils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root sandbox user
RUN groupadd -g 1000 sandbox && \
    useradd -u 1000 -g 1000 -m -s /bin/sh sandbox

# /tmp is mounted as tmpfs at runtime; ensure it exists
RUN mkdir -p /tmp && chmod 1777 /tmp

USER sandbox
WORKDIR /tmp
