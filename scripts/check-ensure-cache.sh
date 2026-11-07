#!/usr/bin/env bash
set -uo pipefail
F=/home/yk/PS5MM/third_party/llama.cpp/tools/mtmd/mtmd-helper-gen.cpp
echo "==== ensure_cache 全文 ===="
grep -n -A45 'bool ensure_cache' "$F" | head -60
