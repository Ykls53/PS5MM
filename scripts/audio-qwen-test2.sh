#!/usr/bin/env bash
# Base 版需要参考音频（voice clone）。用刚生成的那段 wav 当参考，看能不能出声。
set -uo pipefail
cd /home/yk/ext/audio.cpp || exit 1
M=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/_deploy-tmp/audio-qwen3/qwen3-tts-12hz-0.6b-base-q8_0.gguf
timeout 1200 build-vulkan/bin/audiocpp_cli --task tts --family qwen3_tts --model "$M" \
    --backend cpu --threads 8 --text "你好，我是大肥鱼。" --language chinese \
    --voice-ref /tmp/tts-zh.wav --reference-text "你好，我是大肥鱼，今天也在帮你干活。" \
    --out /tmp/qwen-zh.wav --metrics 2>&1 | tail -14
ls -l /tmp/qwen-zh.wav 2>/dev/null || echo "(no wav)"
