#!/usr/bin/env bash
set -uo pipefail
D=/home/yk/PS5MM/ps5/app/dashboard.cpp
echo "==== 卡片进度条 / 内存条相关 ===="
grep -n 'progress\|bar\|进度\|内存\|free_gib\|model_gib' "$D" | head -50
