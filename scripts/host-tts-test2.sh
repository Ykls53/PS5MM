#!/usr/bin/env bash
# The speech engine, end to end, on the PC. The load takes a minute or two on a
# CPU-only machine, so this waits for /health instead of guessing.
set -uo pipefail
cd /home/yk/PS5MM
export LD_LIBRARY_PATH="$PWD/third_party/llama.cpp/build-pc/bin:${LD_LIBRARY_PATH:-}"
export PS5MM_TTS_NGL=${PS5MM_TTS_NGL:-0}
export PS5MM_NO_CAPS=${PS5MM_NO_CAPS:-1}

pkill -f 'build/host/tts_probe' 2>/dev/null
pkill -f 'gdb -q -batch' 2>/dev/null
pkill -f 'build/host/ps5mm-host' 2>/dev/null
sleep 2
nohup build/host/ps5mm-host --settings /data/PS5MM/settings.json > /tmp/ps5mm-host.log 2>&1 &
echo "host started, waiting for the speech engine on :8003 (up to 8 min)"
code=000
for i in $(seq 1 480); do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 2 http://127.0.0.1:8003/health 2>/dev/null)
    [ "$code" = "200" ] && { echo "tts ready after ${i}s"; break; }
    sleep 1
done
echo "health=$code"
curl -s -m 10 http://127.0.0.1:8003/health; echo
echo "==== voices ===="
curl -s -m 10 http://127.0.0.1:8003/v1/audio/voices; echo
echo "==== speech (zh) ===="
curl -s -m 600 -X POST http://127.0.0.1:8003/v1/audio/speech \
    -H 'Content-Type: application/json' \
    -d '{"input":"你好，我是大肥鱼，今天也在帮你干活。","lang":"zh"}' \
    -o /tmp/tts-zh.wav -w 'http=%{http_code} bytes=%{size_download} time=%{time_total}\n'
ls -l /tmp/tts-zh.wav 2>/dev/null
file /tmp/tts-zh.wav 2>/dev/null
echo "==== engine log ===="
grep -E 'ps5mm-tts' /tmp/ps5mm-host.log | tail -8
