#!/usr/bin/env bash
# Runs scripts/build-host.sh and prints only what matters.
set -uo pipefail
cd /home/yk/PS5MM
timeout 900 bash scripts/build-host.sh > /tmp/build-host.log 2>&1
rc=$?
echo "EXIT=$rc"
grep -nE 'error:|undefined reference|No such file' /tmp/build-host.log | head -30
echo "---- tail ----"
tail -6 /tmp/build-host.log
exit $rc
