#!/usr/bin/env bash
set -uo pipefail
echo "==== processes ===="
ps -ef | grep -E 'ps5mm-host' | grep -v grep || echo "(none)"
echo "==== full log ===="
cat /tmp/ps5mm-host.log 2>/dev/null | tail -60
echo "==== dmesg tail ===="
dmesg 2>/dev/null | tail -5
