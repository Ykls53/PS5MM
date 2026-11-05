#!/usr/bin/env bash
# Collects the console deliverables in one folder on the D: drive.
set -uo pipefail
SRC=/home/yk/PS5MM/build/app-ps5/title/PPSA99577
D=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/deliver-20261105
mkdir -p "$D"
cp -f "$SRC/eboot.bin" "$D/eboot.bin"
cp -f "$SRC/sce_sys/param.json" "$D/param.json"
cp -f /home/yk/PS5MM/ps5/host/host-verify.py "$D/host-verify.py" 2>/dev/null || true
(cd "$D" && sha256sum eboot.bin > eboot.sha256)
echo "==== delivered ===="
ls -l "$D"
echo "==== checksum ===="
cat "$D/eboot.sha256"
echo "==== local video model sizes (to upload later) ===="
ls -l /mnt/d/deepseekDAIGirlfriend/_research/PS5MM/_deploy-tmp/wan21/
