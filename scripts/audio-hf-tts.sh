#!/usr/bin/env bash
set -uo pipefail
echo "==== TTS families in audio.cpp-gguf ===="
curl -sS --max-time 40 "https://hf-mirror.com/api/models/audio-cpp/audio.cpp-gguf/tree/main" \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
paths=[it.get("path","") for it in d]
for p in paths:
    if any(k in p.lower() for k in ("qwen","tts","kitten","soprano")):
        print(p)
'
echo "==== qwen3 tts dir contents ===="
for d in Qwen3-TTS-GGUF qwen3-tts-GGUF Qwen3TTS-GGUF; do
    out=$(curl -sS --max-time 30 "https://hf-mirror.com/api/models/audio-cpp/audio.cpp-gguf/tree/main/$d" 2>/dev/null)
    if echo "$out" | grep -q '"path"'; then
        echo "--- $d"
        echo "$out" | python3 -c '
import json,sys
d=json.load(sys.stdin)
for it in d:
    print(" ", it.get("type"), it.get("path"), it.get("size",""))
'
    fi
done
