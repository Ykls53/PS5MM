#!/usr/bin/env bash
# 看 main.cpp 的语音槽和 tts_server 的关键行，和我"恢复"的版本对比
set -uo pipefail
M=/home/yk/PS5MM/ps5/app/main.cpp
T=/home/yk/PS5MM/ps5/app/tts_server.cpp
echo "==== main.cpp speech slot ===="
grep -n -A6 'tts_server_start' "$M" | head -40
echo "==== main.cpp tts_model / tts_codec 定义 ===="
grep -n 'tts_model\|tts_codec\|boot_speech\|voices_dir' "$M" | head -20
echo "==== tts_server ngl block ===="
sed -n '294,320p' "$T"
echo "==== tts_server flash_attn ===="
grep -n 'flash_attn' "$T"
