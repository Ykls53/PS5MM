#!/usr/bin/env bash
# 查 interp_server.cpp 里还剩哪些 GPU 相关依赖
set -uo pipefail
F=/home/yk/PS5MM/ps5/app/interp_server.cpp
echo "==== includes ===="
grep -n '#include' "$F"
echo "==== gpu / gpuid ===="
grep -n 'gpu' "$F"
echo "==== lines 155-180 ===="
sed -n '155,180p' "$F"
