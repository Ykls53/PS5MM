#!/usr/bin/env bash
# Two questions: can plain llama.cpp load the TTS backbone at all, and what does
# the loader say before it dies?
set -uo pipefail
L=/home/yk/PS5MM/third_party/llama.cpp/build-pc/bin
export LD_LIBRARY_PATH="$L:${LD_LIBRARY_PATH:-}"
M=/data/PS5MM/tts/backbone.gguf
P=/data/PS5MM/tts/mmproj.gguf
echo "==== files ===="
ls -l "$M" "$P"
echo "==== llama-cli, backbone only, ngl 0 ===="
timeout 300 "$L/llama-cli" -m "$M" -p "hi" -n 2 -ngl 0 --no-warmup > /tmp/tts-cli1.log 2>&1
echo "exit=$?"
grep -nE 'error|abort|not enough|arch|model type|failed|load' /tmp/tts-cli1.log | tail -12
echo "---- tail ----"
tail -6 /tmp/tts-cli1.log
echo "==== llama-cli with mmproj ===="
timeout 300 "$L/llama-cli" -m "$M" -mm "$P" -p "hi" -n 2 -ngl 0 --no-warmup > /tmp/tts-cli2.log 2>&1
echo "exit=$?"
grep -nE 'error|abort|not enough|mtmd|clip|failed' /tmp/tts-cli2.log | tail -12
tail -6 /tmp/tts-cli2.log
