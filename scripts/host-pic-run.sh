#!/usr/bin/env bash
# Runs the picture smoke test and reports what the log said meanwhile.
set -uo pipefail
cd /home/yk/PS5MM
python3 ps5/host/host-pic-test.py "$@"
echo "---- host log ----"
tail -12 /tmp/ps5mm-host.log
