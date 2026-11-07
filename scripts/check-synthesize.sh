#!/usr/bin/env bash
set -uo pipefail
T=/home/yk/PS5MM/ps5/app/tts_server.cpp
echo "==== synthesize 全文 ===="
sed -n '/^bool synthesize/,/^}/p' "$T"
echo
echo "==== 有没有清 KV 的调用 ===="
grep -n 'memory_clear\|kv_cache\|llama_kv\|reset' "$T"
