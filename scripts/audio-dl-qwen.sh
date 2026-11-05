#!/usr/bin/env bash
# Qwen3-TTS 0.6B q8_0: the smallest audio.cpp package that speaks without
# eSpeak-NG (it tokenises text directly instead of phonemising it).
set -uo pipefail
D=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/_deploy-tmp/audio-qwen3
mkdir -p "$D"
URL="https://hf-mirror.com/audio-cpp/audio.cpp-gguf/resolve/main/Qwen3-TTS-12Hz-0.6B-Base-GGUF/qwen3-tts-12hz-0.6b-base-q8_0.gguf"
OUT="$D/qwen3-tts-12hz-0.6b-base-q8_0.gguf"
if [ -f "$OUT" ] && [ "$(stat -c %s "$OUT")" -gt 1900000000 ]; then
    echo "already downloaded: $(stat -c %s "$OUT") bytes"
    exit 0
fi
echo "downloading to $OUT"
timeout 1800 python3 /mnt/d/deepseekDAIGirlfriend/_research/PS5MM/src/dl-multi.py "$URL" "$OUT" 8 > /tmp/audio-dl.log 2>&1
echo "exit=$?"
tail -4 /tmp/audio-dl.log
ls -l "$OUT" 2>/dev/null || echo "(no file)"
