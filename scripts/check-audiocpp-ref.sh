#!/usr/bin/env bash
set -uo pipefail
M=/home/yk/PS5MM/ps5/app/main.cpp
echo "==== audiocpp 相关引用 ===="
grep -n 'audiocpp' "$M"
echo
echo "==== 上下文 ===="
grep -n -B8 -A8 'audiocpp_abi_version' "$M"
