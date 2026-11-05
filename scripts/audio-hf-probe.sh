#!/usr/bin/env bash
# What audio.cpp GGUF packages exist for models that do NOT need eSpeak?
set -uo pipefail
echo "==== hf-mirror tree: audio.cpp-gguf ===="
curl -sS --max-time 30 "https://hf-mirror.com/api/models/audio-cpp/audio.cpp-gguf/tree/main" \
  | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
except Exception as e:
    print("parse failed:", e); raise SystemExit
for it in d:
    print(it.get("type"), it.get("path"), it.get("size",""))
' 2>&1 | head -40
