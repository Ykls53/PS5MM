#!/usr/bin/env bash
# Push the qwen3-tts model (1.99 GB) to the console from the WSL side.
set -uo pipefail
python3 - <<'PY'
import ftplib, os
SRC = "/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/_deploy-tmp/audio-qwen3/qwen3-tts-12hz-0.6b-base-q8_0.gguf"
DST = "/data/PS5MM/audio/qwen3-tts-12hz-0.6b-base-q8_0.gguf"
want = os.path.getsize(SRC)
print(f"local {want} bytes ({want/1e9:.2f} GB)")
f = ftplib.FTP()
f.connect("192.168.5.50", 2121, timeout=20)
f.login()
f.sock.settimeout(1800)
try:
    f.voidcmd("TYPE I")
    have = f.size(DST)
except Exception:
    have = None
if have == want:
    print("already there")
else:
    print(f"uploading (have {have}) ...")
    with open(SRC, "rb") as fh:
        f.storbinary(f"STOR {DST}", fh, blocksize=1024 * 1024)
    print("remote:", f.size(DST))
f.quit()
PY
