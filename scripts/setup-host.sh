#!/usr/bin/env bash
# Puts the PC's model files where the console keeps them (/data/PS5MM/...), so
# the very same settings.json and the very same code paths are exercised.
# Symlinks only: nothing is copied, nothing on the PC is modified.
#
#   bash scripts/setup-host.sh          (run once; needs root for /data)
set -euo pipefail

R=/home/yk/ps5mm-root
D=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/_deploy-tmp
M=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM

mkdir -p "$R"/sd "$R"/models "$R"/tts "$R"/audio "$R"/rife "$R"/trellis "$R"/outputs "$R"/voices

link() {
    [ -e "$2" ] || { echo "setup-host: missing $2" >&2; return 0; }
    ln -sfn "$2" "$1"
}

# image model set (SD1.5 split components)
link "$R/sd/sd15-unet.safetensors"    "$D/sd-extra/sd15-unet.safetensors"
link "$R/sd/sd15-clip-l.safetensors"  "$D/sd-extra/sd15-clip-l.safetensors"
link "$R/sd/sd15-vae.safetensors"     "$D/sd-extra/sd15-vae.safetensors"
# video model set (Wan 2.1 T2V 1.3B, the small one)
link "$R/sd/wan2.1_t2v_1.3B_fp16.safetensors" "$D/wan21/wan2.1_t2v_1.3B_fp16.safetensors"
link "$R/sd/umt5-xxl-encoder-Q4_K_M.gguf"     "$D/wan21/umt5-xxl-encoder-Q4_K_M.gguf"
link "$R/sd/wan_2.1_vae.safetensors"          "$D/wan21/wan_2.1_vae.safetensors"
# text / speech models
link "$R/models/Qwen3-0.6B-Q8_0.gguf"                 "$M/models/Qwen3-0.6B-Q8_0.gguf"
link "$R/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"   "$M/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
link "$R/tts/backbone.gguf"      "$M/models/Qwen3-TTS-12Hz-1.7B-Base-Q4_K_M.gguf"
link "$R/tts/mmproj.gguf"        "$M/models/mmproj-Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf"
link "$R/tts/audio-model.gguf"   "$M/models/kitten-tts-mini-0.8.gguf"
# audio engine model
link "$R/audio/model.gguf"       "$M/models/kitten-tts-mini-0.8.gguf"
# RIFE v4.6
link "$R/rife/flownet.bin"   "$D/rife-v4.6/flownet.bin"
link "$R/rife/flownet.param" "$D/rife-v4.6/flownet.param"

echo "setup-host: layout at $R"
# The console path itself, so one settings.json works on both machines.
mkdir -p /data
ln -sfn "$R" /data/PS5MM
ls -ld /data/PS5MM
ls -l "$R"/sd "$R"/tts | sed -n '1,20p'
