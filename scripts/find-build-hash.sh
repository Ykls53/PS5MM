#!/usr/bin/env bash
# eboot 里嵌的 hash 是从哪来的？找生成它的地方
set -uo pipefail
R=/home/yk/PS5MM
echo "==== 搜 build hash / commit id 的生成处 ===="
grep -rn 'git rev-parse\|GIT_COMMIT\|git describe\|PS5LM_VERSION' "$R/scripts" "$R/ps5/app" 2>/dev/null | head -20

echo
echo "==== 当前 git HEAD ===="
git -C "$R" rev-parse HEAD 2>&1

echo
echo "==== 能不能从 hash 反查 commit ===="
git -C "$R" cat-file -t e900fe751a24c9e3d30ab90969d4714ffc0722d 2>&1 | head -3
