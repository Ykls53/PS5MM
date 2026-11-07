#!/usr/bin/env bash
set -uo pipefail
S=/home/yk/PS5MM/ps5/app/sd_server.cpp
echo "==== on_txt2vid 全文 ===="
grep -n -A45 'void on_txt2vid' "$S"
echo
echo "==== ensure_ctx 签名 ===="
grep -n -B2 -A6 'ensure_ctx' "$S" | head -30
