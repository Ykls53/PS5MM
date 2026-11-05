#!/usr/bin/env bash
# One sentence through the PC build of the speech engine. Short on purpose.
set -uo pipefail
cd /home/yk/PS5MM
export LD_LIBRARY_PATH="$PWD/third_party/llama.cpp/build-pc/bin:${LD_LIBRARY_PATH:-}"
pkill -f 'build/host/ps5mm-tts' 2>/dev/null
pkill -f 'build/host/ps5mm-host' 2>/dev/null
sleep 1
nohup build/host/ps5mm-tts --settings /data/PS5MM/settings.json > /tmp/tts-quick.log 2>&1 &
code=000
for i in $(seq 1 120); do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 2 http://127.0.0.1:8003/health 2>/dev/null)
    [ "$code" = "200" ] && break
    sleep 1
done
echo "health=$code"
grep -E 'n_gpu_layers|loaded in' /tmp/tts-quick.log | tail -3
curl -s -m 300 -X POST http://127.0.0.1:8003/v1/audio/speech \
    -H 'Content-Type: application/json' \
    -d '{"input":"你好，我是大肥鱼。","lang":"zh"}' \
    -o /tmp/tts-quick.wav -w 'http=%{http_code} bytes=%{size_download} time=%{time_total}\n'
ls -l /tmp/tts-quick.wav 2>/dev/null
pkill -f 'build/host/ps5mm-tts' 2>/dev/null
echo done
