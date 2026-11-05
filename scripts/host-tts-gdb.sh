#!/usr/bin/env bash
# Catch the abort inside the real host process, not the probe.
set -uo pipefail
cd /home/yk/PS5MM
export LD_LIBRARY_PATH="$PWD/third_party/llama.cpp/build-pc/bin:${LD_LIBRARY_PATH:-}"
export PS5MM_TTS_NGL=${PS5MM_TTS_NGL:-0}
pkill -f 'gdb -q' 2>/dev/null
pkill -f 'build/host/ps5mm-host' 2>/dev/null
sleep 2
timeout 420 gdb -q -batch -ex run -ex 'bt 22' \
    --args build/host/ps5mm-host --settings /data/PS5MM/settings.json > /tmp/tts-gdb.log 2>&1
echo "gdb exit=$?"
grep -vE '^\[New LWP|^\[Thread|debuginfod' /tmp/tts-gdb.log | tail -45
