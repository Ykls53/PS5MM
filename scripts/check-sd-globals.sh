#!/usr/bin/env bash
set -uo pipefail
S=/home/yk/PS5MM/ps5/app/sd_server.cpp
echo "==== 全局变量（g_svr / g_thread / g_stop）===="
grep -n 'g_svr\|g_thread\|g_stop\|httplib::Server' "$S" | head -20
echo
echo "==== sd_server_start 尾部（listen 怎么起的）===="
sed -n '1029,1090p' "$S"
