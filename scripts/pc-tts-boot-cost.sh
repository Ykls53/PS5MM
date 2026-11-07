#!/usr/bin/env bash
# 量「重启一个 tts 进程到可用」要多久，以及 fork/exec vs 模型加载各占多少
set -uo pipefail
cd /home/yk/PS5MM
export LD_LIBRARY_PATH="$PWD/third_party/llama.cpp/build-pc/bin:${LD_LIBRARY_PATH:-}"

measure_once() {
    local n=$1
    pkill -f 'build/host/ps5mm-tts' 2>/dev/null
    sleep 0.3

    local t_fork=$(date +%s%N)
    nohup build/host/ps5mm-tts --settings /data/PS5MM/settings.json > /tmp/tts-boot-$n.log 2>&1 &
    local pid=$!

    # 等端口
    local t_up=0
    for i in $(seq 1 400); do
        local c=$(curl -s -o /dev/null -w '%{http_code}' -m 1 http://127.0.0.1:8003/health 2>/dev/null)
        if [ "$c" = "200" ]; then
            t_up=$(date +%s%N)
            break
        fi
        sleep 0.1
    done

    local boot_ms=$(( (t_up - t_fork) / 1000000 ))

    # 立刻打一句，量「加载完之后第一句」多久
    local t_s0=$(date +%s%N)
    curl -s -m 200 -X POST http://127.0.0.1:8003/v1/audio/speech \
        -H 'Content-Type: application/json' \
        -d '{"input":"第一句。","lang":"zh"}' -o /tmp/boot-$n.wav -w '%{http_code}' > /tmp/boot-code-$n 2>&1
    local t_s1=$(date +%s%N)
    local speak_ms=$(( (t_s1 - t_s0) / 1000000 ))

    printf '  第%s轮: 起进程到可用 %5d ms, 第一句合成 %5d ms, 合计 %5d ms\n' \
        "$n" "$boot_ms" "$speak_ms" "$((boot_ms + speak_ms))"
}

echo "==== 连启 4 次，量启动耗时（模型已进 page cache，这是最乐观情况）===="
for n in 1 2 3 4; do
    measure_once $n
done

echo
echo "==== 冷缓存参考：丢掉 page cache 后启动一次 ===="
sync
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null && echo "  (cache 已丢)" || echo "  (没有权限丢 cache，跳过)"
measure_once cold

pkill -f 'build/host/ps5mm-tts' 2>/dev/null
