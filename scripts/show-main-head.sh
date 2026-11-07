#!/usr/bin/env bash
set -uo pipefail
M=/home/yk/PS5MM/ps5/app/main.cpp
echo "==== main 之后紧接的 3 行 ===="
sed -n "$(grep -n '^int main' "$M" | cut -d: -f1),+4p" "$M" | cat -A | head -8
