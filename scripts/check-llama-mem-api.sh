#!/usr/bin/env bash
set -uo pipefail
H=/home/yk/PS5MM/third_party/llama.cpp/include/llama.h
echo "==== memory / cache 相关 API ===="
grep -n 'llama_memory_\|llama_kv_\|memory_clear\|memory_seq\|state_save\|state_load' "$H" | head -30
