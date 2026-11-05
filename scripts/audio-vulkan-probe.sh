#!/usr/bin/env bash
# Can audio.cpp see a Vulkan device in WSL? If yes, the GPU path is testable
# here (on llvmpipe) instead of first on the console.
set -uo pipefail
cd /home/yk/ext/audio.cpp || exit 1
echo "==== --list-devices ===="
timeout 120 build-vulkan/bin/audiocpp_cli --list-devices 2>&1 | head -20
echo "==== ICD files ===="
ls /usr/share/vulkan/icd.d/ 2>/dev/null
echo "==== vulkaninfo? ===="
command -v vulkaninfo >/dev/null && timeout 60 vulkaninfo --summary 2>&1 | head -12 || echo "(no vulkaninfo)"
echo "==== qwen3 tts with --backend vulkan ===="
M=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/_deploy-tmp/audio-qwen3/qwen3-tts-12hz-0.6b-base-q8_0.gguf
timeout 600 build-vulkan/bin/audiocpp_cli --task tts --family qwen3_tts --model "$M" \
    --backend vulkan --threads 4 --text "你好，我是大肥鱼。" --language chinese \
    --voice-ref /tmp/tts-short1.wav --reference-text "你好，我是大肥鱼。" \
    --out /tmp/qwen-vk.wav --metrics 2>&1 | tail -12
ls -l /tmp/qwen-vk.wav 2>/dev/null || echo "(no wav)"
