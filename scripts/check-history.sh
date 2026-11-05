#!/usr/bin/env bash
# Is there any way back to the 11-04 sources? git first, then the .bak litter.
set -uo pipefail
R=/home/yk/PS5MM
echo "==== is it a git repo? ===="
git -C "$R" rev-parse --is-inside-work-tree 2>&1 | head -2
echo "==== recent commits ===="
git -C "$R" log --oneline -12 2>&1 | head -14
echo "==== dirty files (what this session touched) ===="
git -C "$R" status --porcelain 2>&1 | head -30
echo "==== .bak files in ps5/app, newest first ===="
ls -lt "$R"/ps5/app/*.bak* 2>/dev/null | head -25
