#!/usr/bin/env bash
set -uo pipefail
for d in Qwen3-TTS-12Hz-0.6B-Base-GGUF Qwen3-TTS-12Hz-1.7B-Base-GGUF KittenTTS-GGUF; do
    echo "==== $d ===="
    curl -sS --max-time 40 "https://hf-mirror.com/api/models/audio-cpp/audio.cpp-gguf/tree/main/$d" \
      | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
except Exception as e:
    print("  parse failed"); raise SystemExit
for it in d:
    sz = it.get("size") or 0
    print(f"  {it.get(\"type\"):9s} {it.get(\"path\"):60s} {sz/1e6:8.1f} MB")
'
done
