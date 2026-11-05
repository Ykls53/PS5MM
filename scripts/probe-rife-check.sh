#!/usr/bin/env bash
set -uo pipefail
R=/home/yk/ext/rife-ncnn/src/rife.cpp
echo "==== outimage.create sites ===="
grep -n 'outimage.create' "$R"
echo "==== PS5MM markers ===="
grep -c 'PS5MM' "$R"
