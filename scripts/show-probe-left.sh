#!/usr/bin/env bash
set -uo pipefail
F=/home/yk/PS5MM/ps5/app/main.cpp
echo "==== 残留的探针相关行 ===="
grep -n 'probe_exec_self\|ps5mm-probe\|probe-exec\|probe_exec\|exec_self\|--probe' "$F" | head -40
