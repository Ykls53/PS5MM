#!/usr/bin/env bash
set -uo pipefail
M=/home/yk/PS5MM/ps5/app/main.cpp
echo "==== 1300-1350 行（音频卡）===="
sed -n '1300,1350p' "$M"
echo
echo "==== 1380-1420 行（引擎过滤）===="
sed -n '1380,1420p' "$M"
