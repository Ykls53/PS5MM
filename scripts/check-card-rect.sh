#!/usr/bin/env bash
set -uo pipefail
D=/home/yk/PS5MM/ps5/app/dashboard.cpp
echo "==== 1820-1870（卡片矩形分配）===="
sed -n '1820,1870p' "$D"
echo
echo "==== kDockY / bottom 定义 ===="
grep -n 'kDockY\|const float bottom\|float bottom' "$D" | head -10
