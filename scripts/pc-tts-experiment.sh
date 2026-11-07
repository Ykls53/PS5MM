#!/usr/bin/env bash
# 三个决定性实验：
#   A. 连打 2 次（确认退化）
#   B. 停 60 秒后再打（看是不是时间能恢复）
#   C. 重启进程再打（看是不是进程级污染）
set -uo pipefail
cd /home/yk/PS5MM
export LD_LIBRARY_PATH="$PWD/third_party/llama.cpp/build-pc/bin:${LD_LIBRARY_PATH:-}"

speak() {
    local tag=$1
    local t0=$(date +%s%N)
    local out=$(curl -s -m 200 -X POST http://127.0.0.1:8003/v1/audio/speech \
        -H 'Content-Type: application/json' \
        -d "{\"input\":\"测试第${tag}句。\",\"lang\":\"zh\"}" \
        -o /tmp/exp-$tag.wav -w '%{http_code} %{size_download}' 2>&1)
    local t1=$(date +%s%N)
    local ms=$(( (t1 - t0) / 1000000 ))
    grep -o 'in [0-9]* ms' /tmp/tts-exp.log | tail -1 | xargs -I{} printf '  [%s] http=%s %6dms  %s\n' "$tag" "${out%% *}" "$ms" "{}"
}

start_tts() {
    pkill -f 'build/host/ps5mm-tts' 2>/dev/null
    sleep 1
    nohup build/host/ps5mm-tts --settings /data/PS5MM/settings.json > /tmp/tts-exp.log 2>&1 &
    for i in $(seq 1 120); do
        c=$(curl -s -o /dev/null -w '%{http_code}' -m 2 http://127.0.0.1:8003/health 2>/dev/null)
        [ "$c" = "200" ] && { echo "  (ready in ${i}s)"; break; }
        sleep 1
    done
}

echo "==== 启动进程 ===="
start_tts

echo
echo "==== A. 连打 2 次 ===="
speak A1
speak A2

echo
echo "==== B. 停 60 秒后再打 ===="
echo "  等待 60 秒..."
sleep 60
speak B1
speak B2

echo
echo "==== C. 重启进程再打 ===="
start_tts
speak C1
speak C2

echo
echo "==== 全部引擎日志 ===="
grep -o 'ps5mm-tts: [0-9]* frames.*in [0-9]* ms' /tmp/tts-exp.log

pkill -f 'build/host/ps5mm-tts' 2>/dev/null
