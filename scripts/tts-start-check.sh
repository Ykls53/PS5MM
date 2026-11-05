#!/usr/bin/env bash
set -uo pipefail
echo "==== is 8098 listening? ===="
curl -s -m 5 -o /tmp/tts-health.json -w 'http=%{http_code}\n' http://127.0.0.1:8098/health
cat /tmp/tts-health.json 2>/dev/null; echo
echo "==== tts_server_start tail (does it join?) ===="
sed -n '/^int tts_server_start/,/^}/p' /home/yk/PS5MM/ps5/app/tts_server.cpp | tail -45
