#!/usr/bin/env bash
set -uo pipefail
echo "==== tts-cli1.log head ===="
head -45 /tmp/tts-cli1.log 2>/dev/null
echo "==== line count ===="
wc -l /tmp/tts-cli1.log 2>/dev/null
