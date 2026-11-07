#!/usr/bin/env python3
"""WSL 侧直接把 build/app-ps5/title/PPSA99577/eboot.bin 传到 PS5，绕开 deploy 目录的旧文件。"""
import ftplib
import os

HOST = "192.168.5.50"
SRC = "/home/yk/PS5MM/build/app-ps5/title/PPSA99577/eboot.bin"
DST = "/data/homebrew/PPSA99577/eboot.bin"

want = os.path.getsize(SRC)
print("local:", want, "bytes")

f = ftplib.FTP()
f.connect(HOST, 2121, timeout=25)
f.login()
f.sock.settimeout(300)
# eboot 必须先 DELE 再传（技能里的规矩）
try:
    f.delete(DST)
    print("deleted old eboot")
except Exception as e:
    print("delete:", type(e).__name__)
with open(SRC, "rb") as fh:
    f.storbinary("STOR " + DST, fh, blocksize=1024 * 1024)
print("uploaded")
try:
    f.voidcmd("TYPE I")
    print("remote size:", f.size(DST))
except Exception as e:
    print("size:", type(e).__name__)
f.quit()
