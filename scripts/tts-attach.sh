#!/usr/bin/env bash
# The probe is alive but idle at 2.6 GB RSS: find out where it is parked.
set -uo pipefail
PID=$(pgrep -f 'build/host/tts_probe' | head -1)
echo "pid=$PID"
if [ -z "$PID" ]; then
    echo "(probe not running)"
    exit 0
fi
gdb -p "$PID" -batch -ex 'thread apply all bt 10' 2>&1 |
    grep -vE '^\[New LWP|debuginfod|^$|^\[Current thread' |
    head -60
