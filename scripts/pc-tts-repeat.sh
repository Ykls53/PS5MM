#!/usr/bin/env bash
# PC 上模拟「PS5 那套链接组合」：ps5mm-tts 是独立二进制，只链 llama，
# 但 PS5 上语音和 sd/trellis 在同一个 image 里。先验最基础的一条：
# 同一个 tts_server.cpp 在 PC 上单进程能不能稳定出音频（多跑几次看间歇性）。
set -uo pipefail
cd /home/yk/PS5MM
export LD_LIBRARY_PATH="$PWD/third_party/llama.cpp/build-pc/bin:${LD_LIBRARY_PATH:-}"

pkill -f 'build/host/ps5mm-tts' 2>/dev/null
sleep 1
nohup build/host/ps5mm-tts --settings /data/PS5MM/settings.json > /tmp/tts-repeat.log 2>&1 &
PID=$!
echo "pid $PID"

for i in $(seq 1 120); do
    c=$(curl -s -o /dev/null -w '%{http_code}' -m 2 http://127.0.0.1:8003/health 2>/dev/null)
    [ "$c" = "200" ] && { echo "ready after ${i}s"; break; }
    sleep 1
done

echo "==== 连打 5 次，看是否间歇性卡 ===="
for n in 1 2 3 4 5; do
    t0=$(date +%s%N)
    out=$(curl -s -m 120 -X POST http://127.0.0.1:8003/v1/audio/speech \
        -H 'Content-Type: application/json' \
        -d "{\"input\":\"第 $n 次测试，看会不会间歇性卡住。\",\"lang\":\"zh\"}" \
        -o /tmp/tts-run-$n.wav -w '%{http_code} %{size_download}' 2>&1)
    t1=$(date +%s%N)
    ms=$(( (t1 - t0) / 1000000 ))
    riff=no
    [ -s /tmp/tts-run-$n.wav ] && [ "$(head -c 4 /tmp/tts-run-$n.wav)" = "RIFF" ] && riff=yes
    printf '  #%d  http=%s  %5dms  riff=%s\n' "$n" "${out%% *}" "$ms" "$riff"
done

echo
echo "==== 引擎日志（关键行）===="
grep -E 'loaded in|listening|frames|init_audio|error' /tmp/tts-repeat.log | tail -12
pkill -f 'build/host/ps5mm-tts' 2>/dev/null
