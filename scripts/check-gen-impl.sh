#!/usr/bin/env bash
set -uo pipefail
F=/home/yk/PS5MM/third_party/llama.cpp/tools/mtmd/mtmd-helper-gen.cpp
echo "==== gen_audio 构造函数 / reset 逻辑 ===="
grep -n -B2 -A40 'struct gen_audio_impl\|class gen_audio_impl' "$F" | head -60
echo
echo "==== 有没有 reset / clear 成员函数 ===="
grep -n 'void reset\|reset()\|clear()' "$F" | head -20
echo
echo "==== 累积型成员变量 ===="
grep -n 'std::vector<float>\|std::vector<int\|resize(' "$F" | head -25
