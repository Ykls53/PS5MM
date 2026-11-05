#!/usr/bin/env python3
"""Full PC verification sweep for the PS5MM engines.

Runs every engine that this host build carries, in the order a user would hit
them, and prints one PASS/FAIL line per check plus a machine-readable JSON tail.
Nothing here restarts the process: a crash shows up as a dead port, which is
exactly what the console must never do.

    python3 ps5/host/host-verify.py [--quick]
"""
import base64
import json
import sys
import threading
import time
import urllib.error
import urllib.request

PIC = "http://127.0.0.1:8002"
CTL = "http://127.0.0.1:8099"
RESULTS = []


def req(url, path, body=None, timeout=1800, raw=False):
    url = url + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET",
                              headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            payload = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            return payload, ctype, time.time() - t0, resp.status
    except urllib.error.HTTPError as e:
        return e.read(), e.headers.get("Content-Type", ""), time.time() - t0, e.code
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}", time.time() - t0, 0


def record(name, ok, detail=""):
    RESULTS.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def alive():
    body, _, _, code = req(CTL, "/alive", timeout=10)
    return code == 200


def check_health():
    body, _, _, code = req(PIC, "/health", timeout=20)
    if code != 200 or body is None:
        return record("picture /health", False, f"code={code}")
    h = json.loads(body)
    record("picture /health", h.get("ok") is True,
           f"loaded={h.get('model_loaded')} video_model={'yes' if h.get('video_model') else 'no'}")


def img(tag, seed=None, size=256):
    body = {"prompt": "a white whale girl, flat illustration, soft light", "steps": 2,
            "width": size, "height": size, "cfg_scale": 5.0}
    if seed is not None:
        body["seed"] = seed
    payload, ctype, dt, code = req(PIC, "/sdapi/v1/txt2img", body)
    if code != 200 or payload is None:
        return record(tag, False, f"code={code} {str(ctype)[:120]}"), None
    imgs = json.loads(payload).get("images") or []
    if not imgs:
        return record(tag, False, "no images"), None
    data = imgs[0]
    blob = base64.b64decode(data.split(",", 1)[1] if data.startswith("data:") else data)
    ok = blob[:8] == b"\x89PNG\r\n\x1a\n"
    record(tag, ok, f"{dt:.1f}s {len(blob)}B png={ok}")
    return ok, data


def video(tag):
    body = {"prompt": "a white whale swimming in a calm blue ocean", "frames": 5,
            "width": 320, "height": 192, "steps": 2, "fps": 8, "flow_shift": 3.0}
    payload, ctype, dt, code = req(PIC, "/sdapi/v1/txt2vid", body)
    ok = code == 200 and payload is not None and payload[:4] == b"RIFF"
    record(tag, ok, f"{dt:.1f}s {len(payload) if payload else 0}B riff={bool(payload and payload[:4] == b'RIFF')}")
    return ok


def interp(f0, f1):
    body = {"frame0": f0, "frame1": f1, "timestep": 0.5}
    payload, ctype, dt, code = req(PIC, "/media/v1/interpolate", body)
    if code != 200 or payload is None:
        return record("RIFE interpolate", False, f"code={code}")
    try:
        blob = base64.b64decode(json.loads(payload)["png"])
    except Exception:  # noqa: BLE001
        return record("RIFE interpolate", False, "no png in response")
    ok = blob[:8] == b"\x89PNG\r\n\x1a\n"
    record("RIFE interpolate", ok, f"{dt:.2f}s {len(blob)}B")
    return ok


def media_info():
    payload, _, _, code = req(PIC, "/media/v1/info", timeout=30)
    record("media /media/v1/info", code == 200 and payload is not None,
           (payload or b"")[:120].decode("utf-8", "replace"))


def concurrent():
    out = {}

    def one(i):
        body = {"prompt": "two whales, flat illustration", "steps": 2, "width": 128, "height": 128}
        payload, _, _, code = req(PIC, "/sdapi/v1/txt2img", body)
        out[i] = code == 200 and payload is not None

    ts = [threading.Thread(target=one, args=(i,)) for i in range(2)]
    t0 = time.time()
    [t.start() for t in ts]
    [t.join() for t in ts]
    record("two requests back to back", all(out.values()), f"{time.time() - t0:.1f}s")


def main():
    quick = "--quick" in sys.argv
    if not alive():
        print("host is not running")
        return 2

    check_health()
    media_info()
    ok1, f0 = img("txt2img #1 (SD1.5)")
    ok2, f1 = img("txt2img #2 (SD1.5, other seed)", seed=4242)
    if not quick:
        video("txt2vid (Wan 2.1 1.3B)")
        img("txt2img #3 after video (the slot bug)")
    if f0 and f1:
        interp(f0, f1)
    concurrent()
    record("process still alive at the end", alive(), "")

    passed = sum(1 for r in RESULTS if r["ok"])
    print(f"\n{passed}/{len(RESULTS)} checks passed")
    print("JSON " + json.dumps(RESULTS))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
