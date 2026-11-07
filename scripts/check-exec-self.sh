#!/usr/bin/env bash
# PS5 上 fork+exec 自身的前提：/proc/self/exe 可读吗？exec 会被签名拦吗？
set -uo pipefail
A=/home/yk/PS5MM/ps5/app
echo "==== main.cpp 里现有的 fork/exec 用法 ===="
grep -n 'fork\|execl\|execv\|self_exe\|proc/self' "$A/main.cpp" | head -20

echo
echo "==== PS5 SDK 有没有对 exec 的限制（头文件里搜）===="
grep -rn 'execl\|execv' /home/yk/PS5SD/.deps/ps5-opengl-sdk/include 2>/dev/null | head -5
find /home/yk/PS5SD/.deps -name 'unistd.h' 2>/dev/null | head -2

echo
echo "==== 现有的 self path 逻辑 ===="
grep -n -B3 -A8 'ps5mm-tts\|self' /home/yk/PS5MM/ps5/host/host_main.cpp | head -25
