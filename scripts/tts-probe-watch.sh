#!/usr/bin/env bash
set -uo pipefail
echo "==== probe log ===="
cat /tmp/tts-probe.log 2>/dev/null | tail -30
echo "==== process ===="
ps -ef | grep -E 'tts_probe|gdb' | grep -v grep | head -5
echo "==== top cpu ===="
ps -eo pid,pcpu,rss,etime,comm --sort=-pcpu | head -6
