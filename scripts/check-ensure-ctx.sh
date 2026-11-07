#!/usr/bin/env bash
set -uo pipefail
S=/home/yk/PS5MM/ps5/app/sd_server.cpp
echo "==== ensure_ctx 签名和开头 ===="
grep -n -A20 'bool ensure_ctx' "$S" | head -30
echo
echo "==== 调用处 ===="
grep -n 'ensure_ctx(' "$S"
