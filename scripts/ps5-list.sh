#!/usr/bin/env bash
# One FTP connection, one look at everything we are about to touch. Repeated
# LISTs annoy ftpsrv, so this asks exactly once.
set -uo pipefail
IP=${1:-192.168.5.50}
python3 - "$IP" <<'PY'
import sys
from ftplib import FTP

ftp = FTP()
ftp.connect(sys.argv[1], 2121, timeout=15)
ftp.login()

def ls(path, limit=40):
    print(f"---- {path}")
    try:
        lines = []
        ftp.retrlines(f"LIST {path}", lines.append)
        for l in lines[:limit]:
            print("   ", l)
    except Exception as e:
        print("    ERR", type(e).__name__, e)

ls("/data/homebrew/PPSA99577")
ls("/data/PS5MM/sd")
ls("/data/PS5MM/audio")
ls("/data/PS5MM/tts")
ls("/data/PS5SD/models/diffusion_models", 8)
ftp.quit()
PY
