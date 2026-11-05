#!/usr/bin/env bash
# Confirm the new eboot carries the GPU-first changes, then refresh the
# deliverables (deploy folder + deliver folder).
set -uo pipefail
ELF=/home/yk/PS5MM/build/app-ps5/eboot.elf
BIN=/home/yk/PS5MM/build/app-ps5/title/PPSA99577/eboot.bin
D=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/deliver-20261105
DEP=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/deploy/PPSA99577

echo "==== markers ===="
python3 - "$ELF" <<'PY'
import sys
data = open(sys.argv[1], 'rb').read()
for m in [
    b'ps5mm-interp: ncnn gpu',
    b'ncnn sees no Vulkan device',
    b'ps5mm-audio: vulkan session failed',
    b'ps5mm-tts: n_gpu_layers',
    b'switching model set',
    '视频编码器'.encode(),
]:
    print(("YES  " if m in data else "no   ") + m.decode('utf-8', 'replace'))
PY

echo "==== sizes / sha ===="
stat -c '%s %n' "$BIN"
sha256sum "$BIN"

echo "==== refresh deliverables ===="
cp -f "$BIN" "$D/eboot.bin"
cp -f "$BIN" "$DEP/eboot.bin"
(cd "$D" && sha256sum eboot.bin > eboot.sha256)
ls -l "$D" | sed -n '1,12p'
