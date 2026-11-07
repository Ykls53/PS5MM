#!/usr/bin/env bash
set -uo pipefail
M=/home/yk/PS5MM/ps5/app/main.cpp
echo "==== main() 的签名长什么样 ===="
grep -n 'int main' "$M"
echo
echo "==== 附近几行 ===="
grep -n -B2 -A4 'int main' "$M" | head -20
