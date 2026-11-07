#!/usr/bin/env bash
set -uo pipefail
echo "==== main.cpp 里语音子进程是怎么起的（host 版的 fork 逻辑）===="
H=/home/yk/PS5MM/ps5/host/host_main.cpp
grep -n 'fork\|exec\|ps5mm-tts\|child' "$H" 2>/dev/null | head -20
echo
echo "==== PS5 版 main.cpp 里 tts 是线程还是进程 ===="
grep -n 'tts_server_start\|std::thread.*tts' /home/yk/PS5MM/ps5/app/main.cpp | head -5
