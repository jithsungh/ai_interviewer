# Sandbox image for Python3 code execution
# Provides: python3, /usr/bin/time, timeout, /bin/sh
# Runs as non-root user 1000:1000

FROM python:3.12-slim

# Install GNU time (provides /usr/bin/time -v)
# coreutils already provides 'timeout'
RUN apt-get update && \
    apt-get install -y --no-install-recommends time && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root sandbox user
RUN groupadd -g 1000 sandbox && \
    useradd -u 1000 -g 1000 -m -s /bin/sh sandbox

# /tmp is mounted as tmpfs at runtime; ensure it exists
RUN mkdir -p /tmp && chmod 1777 /tmp

USER sandbox
WORKDIR /tmp
