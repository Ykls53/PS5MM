#!/usr/bin/env bash
set -uo pipefail
R=/home/yk/ext/rife-ncnn/src/rife.cpp
echo "==== process_v4_cpu ===="
awk '/int RIFE::process_v4_cpu/,/^}/' "$R"
echo "==== to_pixels call sites ===="
grep -n 'to_pixels\|from_pixels' "$R"
