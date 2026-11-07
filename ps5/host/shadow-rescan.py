#!/usr/bin/env python3
"""ShadowMount 重扫，让新 eboot 生效。

先 DELE（这次用不同姿势），再 POST /api/v1/scan，然后回读大小确认。
"""
import ftplib
import io
import json
import urllib.request

HOST = "192.168.5.50"

# 1. 删掉盘上的 eboot（ftpsrv 的 DELE 会报 error_reply 但实际删了，再确认）
f = ftplib.FTP()
f.connect(HOST, 2121, timeout=25)
f.login()
f.sock.settimeout(180)
try:
    f.delete("/data/homebrew/PPSA99577/eboot.bin")
    print("DELE sent")
except Exception as e:
    print("DELE:", type(e).__name__)
try:
    f.voidcmd("TYPE I")
    print("size after DELE:", f.size("/data/homebrew/PPSA99577/eboot.bin"))
except Exception as e:
    print("size:", type(e).__name__)
f.quit()

# 2. 重新传
SRC = "/home/yk/PS5MM/build/app-ps5/title/PPSA99577/eboot.bin"
print("\nre-upload from WSL is done separately")
