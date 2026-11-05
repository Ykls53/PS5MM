#!/usr/bin/env bash
# Is the audio model itself fine, and only eSpeak missing? Install eSpeak and
# ask the CLI to speak with the same gguf the console has.
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq espeak-ng libespeak-ng1 > /tmp/apt-espeak.log 2>&1
echo "apt exit=$?"
ldconfig -p 2>/dev/null | grep -c espeak
cd /home/yk/ext/audio.cpp || exit 1
timeout 900 build-vulkan/bin/audiocpp_cli --task tts --family kitten_tts \
    --model /data/PS5MM/audio/model.gguf --backend cpu --threads 8 \
    --text "hello, this is the audio engine" --voice-id Matthew \
    --out /tmp/kitten.wav --metrics 2>&1 | tail -12
ls -l /tmp/kitten.wav 2>/dev/null || echo "(no wav)"
