#!/usr/bin/env bash
set -uo pipefail
for d in Qwen3-TTS-12Hz-0.6B-Base-GGUF Qwen3-TTS-12Hz-1.7B-Base-GGUF KittenTTS-GGUF KittenTTS2-GGUF; do
    echo "==== $d ===="
    curl -sS --max-time 40 "https://hf-mirror.com/api/models/audio-cpp/audio.cpp-gguf/tree/main/$d" \
      | python3 -c '
import json, sys
try:
    items = json.load(sys.stdin)
except Exception:
    print("  (no listing / not a directory)")
    raise SystemExit
for it in items:
    kind = it.get("type") or "?"
    path = it.get("path") or "?"
    size = it.get("size") or 0
    print("  %-9s %-58s %8.1f MB" % (kind, path, size / 1e6))
'
done
