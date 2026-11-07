#!/usr/bin/env python3
"""最终一次性流程（WSL 侧，源就在本地）：
   DELE 旧 eboot → 传新 eboot（带探针，位置修正版）
   → 触发 ShadowMount /api/v1/scan 重扫 → launch → 等 → 读结果文件
"""
import ftplib
import io
import json
import time
import urllib.request
import http.cookiejar

HOST = "192.168.5.50"
SRC = "/home/yk/PS5MM/build/app-ps5/title/PPSA99577/eboot.bin"
DST = "/data/homebrew/PPSA99577/eboot.bin"


def ftp_conn():
    f = ftplib.FTP()
    f.connect(HOST, 2121, timeout=25)
    f.login()
    f.sock.settimeout(180)
    return f


def scan():
    base = f"http://{HOST}:10101"
    for body in ({"reset_attempts": True}, {}):
        try:
            req = urllib.request.Request(
                base + "/api/v1/scan", data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                print("  scan", body, "->", r.status, r.read()[:200])
            return True
        except Exception as e:
            print("  scan", body, "->", type(e).__name__)
    return False


def launch():
    base = f"http://{HOST}:8780"
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    r = urllib.request.Request(base + "/api/session", data=b"{}", method="POST")
    for h, v in (("Origin", base), ("Referer", base + "/"), ("Content-Type", "application/json")):
        r.add_header(h, v)
    with op.open(r, timeout=20) as resp:
        csrf = json.loads(resp.read())["csrf"]
    cmd = {"command": "job.enqueue",
           "args": {"kind": "library.launch", "input": {"titleId": "PPSA99577"},
                    "key": "probe-final-%d" % int(time.time())}}
    r = urllib.request.Request(base + "/api/command", data=json.dumps(cmd).encode(), method="POST")
    for h, v in (("Origin", base), ("Referer", base + "/"), ("Content-Type", "application/json"),
                 ("X-TacHen-CSRF", csrf)):
        r.add_header(h, v)
    op.open(r, timeout=30).read()


def main():
    # 1. 确保触发文件在
    f = ftp_conn()
    f.storbinary("STOR /data/PS5MM/probe-exec-request", io.BytesIO(b"go\n"))
    for n in ("/data/PS5MM/probe-exec-result.txt", "/data/PS5MM/probe-exec-ok.txt"):
        try:
            f.delete(n)
        except Exception:
            pass
    # 2. DELE + 重传
    try:
        f.delete(DST)
        print("DELE sent")
    except Exception as e:
        print("DELE:", type(e).__name__)
    with open(SRC, "rb") as fh:
        f.storbinary("STOR " + DST, fh, blocksize=1024 * 1024)
    print("uploaded", SRC)
    f.quit()

    # 3. 重扫
    print("== rescan ==")
    scan()
    time.sleep(4)

    # 4. 关掉旧 app（如果在跑）
    try:
        r = urllib.request.Request(f"http://{HOST}:8099/quit", data=b"", method="POST")
        urllib.request.urlopen(r, timeout=8).read()
        print("old app quit")
        time.sleep(3)
    except Exception as e:
        print("quit:", type(e).__name__)

    # 5. launch
    print("== launch ==")
    launch()
    time.sleep(16)

    # 6. 读结果
    print("== results ==")
    f = ftp_conn()
    for name in ("/data/PS5MM/probe-exec-result.txt", "/data/PS5MM/probe-exec-ok.txt"):
        try:
            buf = io.BytesIO()
            f.retrbinary("RETR " + name, buf.write)
            print(" ", name, "->", buf.getvalue().decode("utf-8", "replace").strip())
        except Exception as e:
            print(" ", name, "->", type(e).__name__)
    print("== app.log probe lines ==")
    try:
        buf = io.BytesIO()
        f.retrbinary("RETR /data/PS5MM/app.log", buf.write)
        for l in buf.getvalue().decode("utf-8", "replace").splitlines():
            if "probe" in l.lower():
                print("  ", l[:160])
    except Exception as e:
        print("  ", type(e).__name__)
    f.quit()


if __name__ == "__main__":
    raise SystemExit(main())
