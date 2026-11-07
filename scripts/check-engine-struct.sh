#!/usr/bin/env bash
set -uo pipefail
T=/home/yk/PS5MM/ps5/app/tts_server.cpp
echo "==== Engine 结构成员 ===="
sed -n '/^struct Engine/,/^};/p' "$T"
echo "==== tts_server_start 签名和 mmproj 变量 ===="
grep -n 'tts_server_start\|mmproj\|mtmd_init_from_file' "$T"
