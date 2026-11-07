#!/usr/bin/env bash
set -uo pipefail
F=/home/yk/PS5MM/third_party/llama.cpp/tools/mtmd/mtmd-helper-gen.cpp
echo "==== tok_embd 怎么填的（340-370 行）===="
sed -n '340,375p' "$F"
echo
echo "==== reset() 到底清了什么（105-130 行）===="
sed -n '105,130p' "$F"
