#!/usr/bin/env bash
# 把 11-04 19:48 备份和现在的 main.cpp 里「语音启动段」抽出来对比
set -uo pipefail
A=/home/yk/PS5MM/ps5/app

echo "################ 11-04 19:48 备份里的语音段 ################"
grep -n -A22 'tts_model = use_list' "$A/main.cpp.bak-display-release" | head -34

echo
echo "################ 现在的语音段 ################"
grep -n -A22 'tts_model = use_list' "$A/main.cpp" | head -34
