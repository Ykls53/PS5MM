#!/usr/bin/env bash
# 找 11-05 01:54 前后的 main.cpp 备份，和现在对比语音启动段
set -uo pipefail
A=/home/yk/PS5MM/ps5/app
echo "==== main.cpp 的备份（按时间）===="
ls -lt "$A"/main.cpp.bak-* 2>/dev/null

echo
echo "==== 各个备份里的语音启动段特征 ===="
for f in "$A"/main.cpp.bak-*; do
    [ -f "$f" ] || continue
    n=$(grep -c 'tts_server_start' "$f" 2>/dev/null || echo 0)
    a=$(grep -c 'audio_server_start' "$f" 2>/dev/null || echo 0)
    v=$(grep -c 'sd_server_start_video' "$f" 2>/dev/null || echo 0)
    printf '%-52s tts=%s audio=%s video=%s\n' "$(basename "$f")" "$n" "$a" "$v"
done
