#!/usr/bin/env bash
# Does the on-disk audio model actually load and speak? The CLI answers that
# without the C API, so "missing model package" and "missing C API build" stop
# being the same question.
set -uo pipefail
cd /home/yk/ext/audio.cpp || exit 1
echo "==== audio_server registry setup ===="
sed -n '38,110p' /home/yk/PS5MM/ps5/app/audio_server.cpp
echo "==== kitten tts via cli ===="
timeout 900 build-vulkan/bin/audiocpp_cli --task tts --family kitten_tts \
    --model /data/PS5MM/audio/model.gguf --backend cpu --threads 8 \
    --text "hello, this is a test of the audio engine" --voice-id Matthew \
    --out /tmp/kitten.wav --metrics 2>&1 | tail -25
echo "EXIT=$?"
ls -l /tmp/kitten.wav 2>/dev/null || echo "(no wav)"
