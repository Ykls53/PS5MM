#!/usr/bin/env bash
set -uo pipefail
F=/home/yk/PS5MM/ps5/app/main.cpp
echo "== main 与探针位置 =="
grep -n -E 'int main|probe-exec-request|probe_exec_self|version.*PS5LM_VERSION' "$F"
echo
echo "== main 开头 40 行 =="
N=$(grep -n 'int main' "$F" | head -1 | cut -d: -f1)
sed -n "${N},$((N+40))p" "$F"
