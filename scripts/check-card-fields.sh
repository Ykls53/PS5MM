#!/usr/bin/env bash
set -uo pipefail
M=/home/yk/PS5MM/ps5/app/main.cpp
echo "==== picture 卡 1278-1300 ===="
sed -n '1278,1300p' "$M"
echo
echo "==== video 卡（我新加的）===="
grep -n -A14 'c.kind     = "video"' "$M"
