#!/usr/bin/env bash
# Is the crash tts_server's fault, or does llama.cpp itself fail on this model
# on a plain CPU build? llama-cli answers that in one shot.
set -uo pipefail
L=/home/yk/PS5MM/third_party/llama.cpp/build-pc/bin
export LD_LIBRARY_PATH="$L:${LD_LIBRARY_PATH:-}"
echo "==== executables ===="
ls -1 "$L" | grep -E '^llama' | head
echo "==== llama-cli on the tts backbone (CPU, ngl 0) ===="
timeout 180 "$L/llama-cli" -m /data/PS5MM/tts/backbone.gguf -p "hi" -n 1 -ngl 0 --no-warmup 2>&1 | tail -20
echo "EXIT=$?"
