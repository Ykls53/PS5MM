#!/usr/bin/env bash
# Audits every engine for "forced CPU" settings: what the console would run on.
set -uo pipefail
A=/home/yk/PS5MM/ps5/app
echo "==== audio: C API load signature (backend argument?) ===="
grep -n 'audiocpp_model_load' -A 8 /home/yk/ext/audio.cpp/include/audiocpp.h 2>/dev/null | head -20
echo "==== audio_server call site ===="
grep -n 'audiocpp_model_load\|audiocpp_registry_create\|backend' "$A/audio_server.cpp" | head -12
echo "==== tts: threads / gpu ===="
grep -n 'n_gpu_layers\|n_threads\|ggml_backend_dev_by_type' "$A/tts_server.cpp" | head -12
echo "==== interp: gpuid ===="
grep -n 'new RIFE\|gpuid\|RIFE(' "$A/interp_server.cpp" | head -8
echo "==== trellis: backend ===="
grep -n 'backend\|Vulkan\|cpu' "$A/trellis_server.cpp" | head -12
echo "==== main.cpp: how sd/audio/trellis are configured ===="
grep -n 'TrellisPaths\|AudioModels\|SdModels' "$A/main.cpp" | head -10
