#!/usr/bin/env bash
# 语音克隆相关的代码：两个引擎各自的参考音频路径怎么走
set -uo pipefail
T=/home/yk/PS5MM/ps5/app/tts_server.cpp
A=/home/yk/PS5MM/ps5/app/audio_server.cpp

echo "==== tts_server（8003）里的 voice / 参考音频 ===="
grep -n 'voice\|speaker\|reference\|bitmap' "$T" | head -30

echo
echo "==== tts_server voice_path 实现 ===="
grep -n -A14 'voice_path' "$T" | head -30

echo
echo "==== audio_server（8004）里的 voice / 克隆 ===="
grep -n 'voice\|clone\|reference\|spkenc' "$A" | head -30
