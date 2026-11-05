#!/usr/bin/env bash
# Rebuild the host binary, restart it, and run the full verification sweep.
set -uo pipefail
cd /home/yk/PS5MM
bash scripts/run-build.sh || exit 1
bash scripts/host-smoke.sh
echo "==== verify ===="
python3 ps5/host/host-verify.py "$@"
rc=$?
echo "==== log tail ===="
tail -10 /tmp/ps5mm-host.log
exit $rc
