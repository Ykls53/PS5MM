#!/usr/bin/env bash
# Push the reference voice from WSL straight to the console.
set -uo pipefail
python3 - <<'PY'
import ftplib, os
f = ftplib.FTP()
f.connect("192.168.5.50", 2121, timeout=20)
f.login()
f.sock.settimeout(300)
try:
    f.mkd("/data/PS5MM/voices")
    print("created /data/PS5MM/voices")
except Exception as e:
    print("voices dir:", type(e).__name__)
src = "/tmp/tts-short1.wav"
print("local:", os.path.getsize(src), "bytes")
with open(src, "rb") as fh:
    f.storbinary("STOR /data/PS5MM/voices/default.wav", fh)
print("remote:", f.size("/data/PS5MM/voices/default.wav"))
lines = []
f.retrlines("LIST /data/PS5MM/voices", lines.append)
for l in lines:
    print("  ", l)
f.quit()
PY
