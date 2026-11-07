#!/usr/bin/env bash
set -uo pipefail
cd /home/yk/PS5MM
export LD_LIBRARY_PATH="$PWD/third_party/llama.cpp/build-pc/bin:${LD_LIBRARY_PATH:-}"
echo "LD=$LD_LIBRARY_PATH"
ls "$PWD/third_party/llama.cpp/build-pc/bin/"*.so* 2>/dev/null | head -5
echo "---- 找 libllama ----"
find "$PWD/third_party/llama.cpp/build-pc" -name 'libllama.so*' 2>/dev/null | head -3
echo "---- 跑探针 ----"
./build/host/ps5mm-host --probe-exec 2>&1 | head -20
