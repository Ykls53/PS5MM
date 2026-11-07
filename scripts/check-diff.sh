#!/usr/bin/env bash
# 两个版本之间到底改了什么：拿 ps5/app 的 git 状态对比
set -uo pipefail
cd /home/yk/PS5MM || exit 1
echo "==== 自 unknown-20261105 以来改过的文件 ===="
git status --porcelain 2>/dev/null | head -30
echo
echo "==== main.cpp 的改动行数 ===="
git diff --stat 2>/dev/null | tail -15
