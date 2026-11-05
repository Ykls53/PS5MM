#!/usr/bin/env bash
# Does the freshly built eboot carry every fix? Look for the marker strings the
# patches added -- an ELF is plain, only the SELF wrapper is sealed.
set -uo pipefail
ELF=/home/yk/PS5MM/build/app-ps5/eboot.elf
BIN=/home/yk/PS5MM/build/app-ps5/title/PPSA99577/eboot.bin
echo "==== sizes ===="
stat -c '%n %s bytes' "$ELF" "$BIN"
echo "==== marker strings (python, utf-8 safe) ===="
python3 - "$ELF" <<'PY'
import sys
data = open(sys.argv[1], 'rb').read()
for marker in [
    b'switching model set',
    b'PS5MM_TTS_NGL',
    b'video_diffusion',
    b'sd_video_t5xxl',
    '视频编码器'.encode(),
    '视频 VAE'.encode(),
    '同图像那套'.encode(),
    b'outimage.create',
    b'PS5MM: hand the whole Mat back',
]:
    print(f"{'YES' if marker in data else 'no ':3s}  {marker.decode('utf-8', 'replace')}")
PY
echo "==== sha256 ===="
sha256sum "$BIN"
