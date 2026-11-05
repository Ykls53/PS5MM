#!/usr/bin/env bash
# 诊断：今天 15 个 patch 各自还能不能 --revert（逆序才安全）
set -uo pipefail
P=/home/yk/PS5MM/ps5/patches
LIST="patch-tts-ngl.py patch-sd-modelsets.py patch-sd-preload-call.py patch-dashboard-video-set.py patch-rife-cpu-output.py patch-rife-gpu-output.py patch-tts-ngl-auto.py patch-gpu-first.py patch-tts-cpu-safe.py patch-tts-mtmd-cpu.py patch-audio-voice-ref.py patch-audio-as-speech.py patch-audio-backend-cpu.py patch-conservative.py patch-tts-mtmd-cpu.py"
for f in $LIST; do
    if [ -f "$P/$f" ]; then
        out=$(python3 "$P/$f" --check 2>&1 | tr '\n' ' ' | cut -c1-100)
        printf '%-34s %s\n' "$f" "$out"
    else
        printf '%-34s MISSING\n' "$f"
    fi
done
echo
echo "==== 当前 interp / tts / main 关键行 ===="
grep -c 'gpu.h' /home/yk/PS5MM/ps5/app/interp_server.cpp || true
grep -n 'n_gpu_layers = 999' /home/yk/PS5MM/ps5/app/tts_server.cpp || true
grep -n 'flash_attn_type' /home/yk/PS5MM/ps5/app/tts_server.cpp || true
