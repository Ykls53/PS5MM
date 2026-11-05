#!/usr/bin/env bash
# Rebuild, restart, and interpolate through the real HTTP route.
set -uo pipefail
cd /home/yk/PS5MM
bash scripts/run-build.sh || exit 1
bash scripts/host-smoke.sh
echo "==== interp test ===="
python3 ps5/host/host-interp-test.py
echo "==== host log tail ===="
tail -8 /tmp/ps5mm-host.log
