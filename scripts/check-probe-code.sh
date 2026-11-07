#!/usr/bin/env bash
set -uo pipefail
M=/home/yk/PS5MM/ps5/app/main.cpp
echo "==== 探针插到哪了 / main 长什么样 ===="
grep -n 'probe_exec_self\|^int main' "$M"
echo
echo "==== main 开头 20 行 ===="
sed -n "$(grep -n '^int main' "$M" | cut -d: -f1),+22p" "$M"
echo
echo "==== 探针函数里的 strcmp 判断 ===="
sed -n "$(grep -n 'static int probe_exec_self' "$M" | cut -d: -f1),+14p" "$M"
