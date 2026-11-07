#!/usr/bin/env bash
set -uo pipefail
cd /home/yk/PS5MM
export LD_LIBRARY_PATH="$PWD/third_party/llama.cpp/build-pc/bin:${LD_LIBRARY_PATH:-}"
echo "==== 探针（PC 上先确认代码对）===="
./build/host/ps5mm-host --probe-exec 2>&1 | head -12
echo "exit=$?"
