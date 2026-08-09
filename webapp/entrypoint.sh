#!/bin/bash
set -e

# Issue #37: Ensure DB files and WAL sidecars on /data are owned by appuser
if [ -d "/data" ] && command -v chown >/dev/null 2>&1; then
    chown -R appuser:appuser /data/*.db* 2>/dev/null || true
    chown -R appuser:appuser /data 2>/dev/null || true
fi

exec "$@"

