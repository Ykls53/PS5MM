#!/usr/bin/env bash
set -uo pipefail
F=/home/yk/PS5MM/ps5/app/main.cpp
echo "== 探针残留数（应为 0 或只有无关字样）=="
grep -c -E 'probe_exec_self|ps5mm-probe|probe-exec-request|probe-exec-ok' "$F" || echo 0
echo
echo "== main 签名 =="
grep -n 'int main' "$F"
echo
echo "== version 行（引擎启动标志，必须在）=="
grep -n 'version.*PS5LM_VERSION' "$F" | head -1
echo
echo "== 语音/视频/3D 引擎启动段是否完好 =="
grep -c 'tts_server_start\|sd_server_start_video\|trellis_server_start' "$F"
