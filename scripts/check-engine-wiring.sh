#!/usr/bin/env bash
# 看引擎编排：sd_server 怎么起、占哪个端口、图片和视频是一套还是两套
set -uo pipefail
M=/home/yk/PS5MM/ps5/app/main.cpp
S=/home/yk/PS5MM/ps5/app/sd_server.hpp
A=/home/yk/PS5MM/ps5/app/audio_server.hpp

echo "==== sd_server.hpp 结构 ===="
cat "$S"

echo
echo "==== main.cpp 里所有 *_server_start 调用 ===="
grep -n '_server_start\|port_of_slot\|slots' "$M" | head -30

echo
echo "==== main.cpp 引擎编排段落（1050-1160）===="
sed -n '1050,1160p' "$M"
