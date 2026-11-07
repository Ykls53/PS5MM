#!/usr/bin/env bash
set -uo pipefail
A=/home/yk/PS5MM/ps5/app
echo "==== EngineCard 结构 ===="
grep -rn -A30 'struct EngineCard' "$A"/*.hpp | head -40
echo
echo "==== main.cpp 里 picture 卡怎么填 width/height/frames/steps ===="
grep -n -B3 -A16 'c.kind    = "picture"' /home/yk/PS5MM/ps5/app/main.cpp
