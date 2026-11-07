#!/usr/bin/env bash
set -uo pipefail
echo "==== run-build.sh 编的是哪个入口 ===="
grep -n 'host_main\|main.cpp\|-o.*ps5mm-host' /home/yk/PS5MM/scripts/run-build.sh 2>/dev/null | head -10

echo
echo "==== build-host.sh 里 ===="
ls /home/yk/PS5MM/scripts/*.sh | head -20
grep -ln 'ps5mm-host' /home/yk/PS5MM/scripts/*.sh 2>/dev/null

echo
echo "==== 找出编 ps5mm-host 的脚本 ===="
for f in /home/yk/PS5MM/scripts/*.sh; do
    if grep -q 'ps5mm-host' "$f" 2>/dev/null; then
        echo "--- $f"
        grep -n 'ps5mm-host\|host_main\|main\.cpp' "$f" | head -8
    fi
done
