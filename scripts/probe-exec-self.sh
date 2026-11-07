#!/usr/bin/env bash
# 独立探针：路径全部写死，不用变量（上一版变量被 PowerShell 吃掉）
set -uo pipefail

SRC=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/src/host/exec_probe_standalone.cpp
OUT=/tmp/exec_probe

echo "==== 源文件 ===="
ls -l /mnt/d/deepseekDAIGirlfriend/_research/PS5MM/src/host/exec_probe_standalone.cpp 2>&1

echo
echo "==== 编译 ===="
g++ -std=c++17 -O1 -o /tmp/exec_probe \
    /mnt/d/deepseekDAIGirlfriend/_research/PS5MM/src/host/exec_probe_standalone.cpp 2>&1
echo "exit=$?"

echo
echo "==== 跑 ===="
if [ -x "$OUT" ]; then
    /tmp/exec_probe 2>&1
    echo "exit=$?"
else
    echo "没编出来"
fi
