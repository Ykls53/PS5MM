#!/usr/bin/env bash
set -uo pipefail
echo "==== /tmp/tts-repeat.log 里所有 ps5mm-tts 行 ===="
grep 'ps5mm-tts' /tmp/tts-repeat.log
