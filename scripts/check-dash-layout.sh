#!/usr/bin/env bash
set -uo pipefail
D=/home/yk/PS5MM/ps5/app/dashboard.cpp
echo "==== 1900-1990（卡片推子 + 底部内存条）===="
sed -n '1900,1990p' "$D"
echo
echo "==== 卡片矩形怎么算的（往上找 Rect 分配）===="
grep -n 'kLeft\|kRight\|kTop\|cards\[\|Rect r{\|Rect{' "$D" | sed -n '1,25p'
