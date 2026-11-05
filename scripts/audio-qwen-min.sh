#!/usr/bin/env bash
# Minimum argument set for qwen3_tts on the CPU: is voice-ref alone enough, or
# does Base also demand reference-text?
set -uo pipefail
cd /home/yk/ext/audio.cpp || exit 1
M=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/_deploy-tmp/audio-qwen3/qwen3-tts-12hz-0.6b-base-q8_0.gguf
REF=/tmp/tts-short1.wav
ls -l "$REF" 2>/dev/null || echo "(no reference wav)"
echo "==== voice-ref only ===="
timeout 900 build-vulkan/bin/audiocpp_cli --task tts --family qwen3_tts --model "$M" \
    --backend cpu --threads 8 --text "今天把语音引擎换成 audio.cpp。" --language chinese \
    --voice-ref "$REF" --out /tmp/q1.wav --metrics 2>&1 | tail -6
ls -l /tmp/q1.wav 2>/dev/null || echo "(no wav)"
echo "==== voice-ref + reference-text ===="
timeout 900 build-vulkan/bin/audiocpp_cli --task tts --family qwen3_tts --model "$M" \
    --backend cpu --threads 8 --text "今天把语音引擎换成 audio.cpp。" --language chinese \
    --voice-ref "$REF" --reference-text "你好，我是大肥鱼。" --out /tmp/q2.wav --metrics 2>&1 | tail -6
ls -l /tmp/q2.wav 2>/dev/null || echo "(no wav)"
