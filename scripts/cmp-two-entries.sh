#!/usr/bin/env bash
# 两个入口的语音启动逻辑差异：app/main.cpp（PS5）vs host/host_main.cpp（PC）
set -uo pipefail

echo "############ PS5 版 ps5/app/main.cpp ############"
grep -n -A6 'tts_server_start\|tts_server_abandon' /home/yk/PS5MM/ps5/app/main.cpp | head -30

echo
echo "############ PC 版 ps5/host/host_main.cpp ############"
grep -n -A8 'tts_pid\|execl\|fork' /home/yk/PS5MM/ps5/host/host_main.cpp | head -40

echo
echo "############ PC 版怎么等子进程就绪 ############"
grep -n 'wait\|ready\|sleep\|health' /home/yk/PS5MM/ps5/host/host_main.cpp | head -15
