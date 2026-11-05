#!/usr/bin/env bash
# Copies the host-main sources from the PC working tree into the build tree,
# and stages the host settings file.
set -euo pipefail
src=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/src/host
dst=/home/yk/PS5MM
mkdir -p "$dst/ps5/host" "$dst/scripts"
cp -f "$src/host_main.cpp" "$src/interp_stub.cpp" "$dst/ps5/host/"
cp -f "$src"/*.cpp "$dst/ps5/host/"
cp -f "$src"/*.py "$dst/ps5/host/"
cp -f "$src"/*.sh "$dst/scripts/"
chmod +x "$dst/scripts/"*.sh
mkdir -p /home/yk/ps5mm-root
cp -f "$src/host-settings.json" /home/yk/ps5mm-root/settings.json
echo "deploy-host-src: ok"
