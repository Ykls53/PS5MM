#!/usr/bin/env bash
set -uo pipefail
B=/home/yk/PS5MM/scripts/build-app.sh
echo "==== audio 相关的所有行 ===="
grep -n 'audio\|ACX_\|audiolibs' "$B"
echo
echo "==== 305-340 行（audio 链接段）===="
sed -n '305,345p' "$B"
