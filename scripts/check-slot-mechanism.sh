#!/usr/bin/env bash
# 槽位/端口自定义机制：settings 里哪些字段、dashboard 怎么用它
set -uo pipefail
APP=/home/yk/PS5MM/ps5/app

echo "==== settings.hpp 里的 slot 字段 ===="
grep -n 'slot' "$APP/settings.hpp"

echo
echo "==== port_of_slot 实现 ===="
grep -rn -A12 'port_of_slot' "$APP/slots.hpp" 2>/dev/null || grep -rn -A12 'port_of_slot' "$APP"/*.hpp | head -30

echo
echo "==== dashboard 里槽位选择（collect_engines / slot 相关）===="
grep -n 'slot\|槽位' "$APP/main.cpp" | sed -n '1,40p'

echo
echo "==== settings.cpp 里 slot 的读写 ===="
grep -n 'slot' "$APP/settings.cpp"
