#!/usr/bin/env bash
# Speech only: load once, speak four times (three short, one long), report each.
# Nothing else is touched, so a failure here points at speech and nothing else.
set -uo pipefail
cd /home/yk/PS5MM
export LD_LIBRARY_PATH="$PWD/third_party/llama.cpp/build-pc/bin:${LD_LIBRARY_PATH:-}"
export PS5MM_TTS_NGL=0

pkill -f 'build/host/ps5mm-tts' 2>/dev/null
pkill -f 'build/host/ps5mm-host' 2>/dev/null
sleep 1
nohup build/host/ps5mm-tts --settings /data/PS5MM/settings.json > /tmp/ps5mm-tts-only.log 2>&1 &
echo "tts pid $!"
code=000
for i in $(seq 1 240); do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 2 http://127.0.0.1:8003/health 2>/dev/null)
    [ "$code" = "200" ] && { echo "ready after ${i}s"; break; }
    sleep 1
done
echo "health=$code"
curl -s -m 5 http://127.0.0.1:8003/health; echo

speak() {
    local tag=$1 text=$2 out=/tmp/tts-$1.wav
    local r
    r=$(curl -s -m 900 -X POST http://127.0.0.1:8003/v1/audio/speech \
        -H 'Content-Type: application/json' \
        -d "{\"input\":\"$text\",\"lang\":\"zh\"}" \
        -o "$out" -w '%{http_code} %{size_download} %{time_total}')
    local code=${r%% *}
    local size=$(stat -c %s "$out" 2>/dev/null || echo 0)
    local riff=no
    [ "$size" -gt 44 ] && [ "$(head -c 4 "$out")" = "RIFF" ] && riff=yes
    printf '%-8s http=%s bytes=%s riff=%s %s\n' "$tag" "$code" "$size" "$riff" "$r"
}

speak short1 "你好，我是大肥鱼。"
speak short2 "今天给你把语音引擎修好了。"
speak short3 "这条不碰显卡，只吃 CPU。"
LONG=$(python3 -c 'print("语音引擎现在跑在中央处理器上，" * 20)')
speak long "$LONG"

# still alive?
sleep 2
code2=$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8003/health 2>/dev/null)
echo "alive after all: health=$code2"
echo "==== engine log ===="
grep -E 'ps5mm-tts' /tmp/ps5mm-tts-only.log | tail -10
pkill -f 'build/host/ps5mm-tts' 2>/dev/null
