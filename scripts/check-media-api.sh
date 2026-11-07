#!/usr/bin/env bash
# 找 /media/v1/frames 的参数名
set -uo pipefail
F=/home/yk/PS5MM/ps5/app/media_server.cpp
echo "==== frames handler ===="
grep -n -A30 'frames' "$F" | head -60
