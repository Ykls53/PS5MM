#!/usr/bin/env bash
# audio.cpp 到底是什么引擎？看它支持哪些 task / 模型家族
set -uo pipefail
echo "==== audio_server 里 task 怎么用的 ===="
grep -n 'task' /home/yk/PS5MM/ps5/app/audio_server.cpp | head -20

echo
echo "==== audio.cpp 的 task 枚举（头文件）===="
grep -n -B3 -A22 'audiocpp_task\|AUDIOCPP_TASK' /home/yk/ext/audio.cpp/include/audiocpp.h | head -50

echo
echo "==== audio.cpp 支持的模型家族 ===="
ls /home/yk/ext/audio.cpp/src/ 2>/dev/null | head -30
