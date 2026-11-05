#!/usr/bin/env bash
# Qwen3-TTS 0.6B through audio.cpp's own CLI: does it speak without eSpeak?
set -uo pipefail
cd /home/yk/ext/audio.cpp || exit 1
M=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/_deploy-tmp/audio-qwen3/qwen3-tts-12hz-0.6b-base-q8_0.gguf
echo "==== inspect ===="
timeout 300 build-vulkan/bin/audiocpp_cli --task tts --family qwen3_tts --model "$M" --inspect 2>&1 | head -20
echo "==== speak (zh) ===="
timeout 1200 build-vulkan/bin/audiocpp_cli --task tts --family qwen3_tts --model "$M" \
    --backend cpu --threads 8 --text "你好，我是大肥鱼。" --language zh \
    --out /tmp/qwen-zh.wav --metrics 2>&1 | tail -14
ls -l /tmp/qwen-zh.wav 2>/dev/null || echo "(no wav)"
