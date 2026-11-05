#!/usr/bin/env bash
set -uo pipefail
A=/home/yk/PS5MM/ps5/app/dashboard.cpp
echo "==== enum block 130-160 ===="
sed -n '130,160p' "$A"
echo "==== rows 190-210 ===="
sed -n '190,210p' "$A"
echo "==== read 540-580 ===="
sed -n '540,580p' "$A"
echo "==== write 695-730 ===="
sed -n '695,730p' "$A"
