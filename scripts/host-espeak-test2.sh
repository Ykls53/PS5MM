#!/usr/bin/env bash
set -uo pipefail
cd /home/yk/ext/audio.cpp || exit 1
echo "==== inspect ===="
timeout 300 build-vulkan/bin/audiocpp_cli --task tts --family kitten_tts \
    --model /data/PS5MM/audio/model.gguf --inspect 2>&1 | head -25
echo "==== speak, default voice ===="
timeout 900 build-vulkan/bin/audiocpp_cli --task tts --family kitten_tts \
    --model /data/PS5MM/audio/model.gguf --backend cpu --threads 8 \
    --text "hello, this is the audio engine" \
    --out /tmp/kitten.wav --metrics 2>&1 | tail -10
ls -l /tmp/kitten.wav 2>/dev/null || echo "(no wav)"
