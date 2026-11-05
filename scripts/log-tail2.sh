#!/usr/bin/env bash
set -uo pipefail
grep -e 'ps5mm-interp' -e 'tts: loaded' -e 'tts: .*wav' /tmp/ps5mm-host.log | tail -10
echo "---- ports ----"
for p in 8002 8003 8099; do
    printf 'port %s -> %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' -m 2 "http://127.0.0.1:$p/" 2>/dev/null)"
done
