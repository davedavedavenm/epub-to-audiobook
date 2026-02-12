#!/bin/bash
set -e

# Fix SSH key/config permissions (bind mounts may have wrong owner/mode)
if [ -d /root/.ssh ]; then
    # Copy mounted SSH files to a writable location with correct permissions
    mkdir -p /tmp/.ssh
    cp -f /root/.ssh/* /tmp/.ssh/ 2>/dev/null || true
    chmod 700 /tmp/.ssh
    chmod 600 /tmp/.ssh/* 2>/dev/null || true

    # Swap in the fixed copy
    rm -rf /root/.ssh
    mv /tmp/.ssh /root/.ssh
fi

exec "$@"
