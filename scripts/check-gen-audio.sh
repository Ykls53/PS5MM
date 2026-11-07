#!/usr/bin/env bash
# gen_audio 内部：每帧往哪写？有没有累积
set -uo pipefail
L=/home/yk/PS5MM/third_party/llama.cpp
F=$(find "$L" -name '*mtmd*audio*' -o -name 'mtmd-helper*' 2>/dev/null | head -5)
echo "候选文件:"
echo "$F"
echo
for f in $F; do
    [ -f "$f" ] || continue
    echo "######## $f"
    grep -n 'step_gen\|struct gen_audio\|frames_\|accum\|push_back\|resize' "$f" | head -25
done
