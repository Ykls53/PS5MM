#!/usr/bin/env bash
# Starts the host binary, waits for the control port, then probes every engine
# port. Leaves the process running (announced at the end).
set -uo pipefail
cd /home/yk/PS5MM
export LD_LIBRARY_PATH="$PWD/third_party/llama.cpp/build-pc/bin:${LD_LIBRARY_PATH:-}"
# The PC has no Vulkan device for llama.cpp; 999 layers aborts inside the loader.
export PS5MM_TTS_NGL=${PS5MM_TTS_NGL:-0}

pkill -f 'build/host/ps5mm-host' 2>/dev/null && sleep 1
nohup build/host/ps5mm-host --settings /data/PS5MM/settings.json > /tmp/ps5mm-host.log 2>&1 &
pid=$!
for _ in $(seq 1 25); do
    if curl -s -m 2 -o /dev/null http://127.0.0.1:8099/alive; then break; fi
    sleep 1
done

echo "PID=$pid"
for p in 8001 8002 8003 8004 8005 8099; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 3 "http://127.0.0.1:$p/" 2>/dev/null)
    echo "port $p -> $code"
done
echo "---- /state ----"
curl -s -m 5 http://127.0.0.1:8099/state
echo "---- log (tail) ----"
tail -25 /tmp/ps5mm-host.log
