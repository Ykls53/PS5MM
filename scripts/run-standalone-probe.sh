#!/usr/bin/env bash
# 先撤回 main.cpp 上的探针（它已经污染了主程序），再用独立探针验
set -uo pipefail
python3 /home/yk/PS5MM/scripts/patch-exec-probe2.py --revert 2>&1 || true
python3 /home/yk/PS5MM/scripts/patch-exec-probe.py --revert 2>&1 || true

echo "==== 确认 main.cpp 干净了 ===="
grep -c 'probe_exec_self\|ps5mm-probe' /home/yk/PS5MM/ps5/app/main.cpp || echo "0 (clean)"

echo
echo "==== 编独立探针 ===="
g++ -std=c++17 -O1 -o /tmp/exec_probe /home/yk/PS5MM/scripts/exec_probe_standalone.cpp && echo "built"
echo
echo "==== 跑 ===="
/tmp/exec_probe 2>&1
