#!/usr/bin/env bash
# 看 sd_server 里的实例结构：是不是全局单例、能不能起第二个
set -uo pipefail
S=/home/yk/PS5MM/ps5/app/sd_server.cpp
echo "==== 全局实例 ===="
grep -n '^struct\|^static\|^Engine\|g_e\b' "$S" | head -25
echo
echo "==== sd_server_start 签名处 ===="
grep -n -A20 'int sd_server_start' "$S" | head -32
