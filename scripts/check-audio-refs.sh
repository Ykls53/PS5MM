#!/usr/bin/env bash
set -uo pipefail
M=/home/yk/PS5MM/ps5/app/main.cpp
echo "==== main.cpp 里所有 audio_ 调用 ===="
grep -n 'audio_server\|audio_slot\|AudioModels\|audio_model' "$M"
