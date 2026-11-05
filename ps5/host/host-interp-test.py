#!/usr/bin/env python3
"""RIFE frame interpolation through the host build.

Two frames out of the picture engine (one per seed), then POST them to
/media/v1/interpolate. A crash here is the SIGSEGV we are chasing: it used to
kill the whole app, so the check also re-reads /health afterwards.
"""
import base64
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8002"


def post(path, body, timeout=1800):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), r.headers.get("Content-Type", ""), time.time() - t0
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read()[:300]}")
    except Exception as e:  # noqa: BLE001
        print(f"  {type(e).__name__}: {e}")
    return None, None, time.time() - t0


def frame(seed, size=256):
    body = {"prompt": "a white whale girl, flat illustration", "steps": 2,
            "width": size, "height": size, "cfg_scale": 5.0, "seed": seed}
    raw, _, dt = post("/sdapi/v1/txt2img", body)
    if raw is None:
        return None
    img = json.loads(raw)["images"][0]
    print(f"  frame seed={seed} {dt:.1f}s {len(img)}B b64")
    return img


def health():
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=10) as r:
            return json.loads(r.read())
    except Exception:  # noqa: BLE001
        return None


def main():
    print("== info before ==")
    raw, _, _ = post("/media/v1/interp/info", {})
    if raw:
        print("  " + raw.decode()[:400])

    print("== frames ==")
    f0 = frame(11)
    f1 = frame(22)
    if not f0 or not f1:
        print("FAIL: could not get two frames")
        return 2

    print("== interpolate ==")
    raw, ctype, dt = post("/media/v1/interpolate", {"frame0": f0, "frame1": f1, "timestep": 0.5}, timeout=1800)
    h = health()
    alive = h is not None
    print(f"  alive_after={alive} {h}")
    if raw is None:
        print("FAIL: no response")
        return 1
    if ctype and "json" in ctype:
        body = json.loads(raw)
        if "png" in body:
            blob = base64.b64decode(body["png"])
            with open("/tmp/interp.png", "wb") as f:
                f.write(blob)
            print(f"  OK {dt:.1f}s png={len(blob)}B -> /tmp/interp.png ({body.get('last_ms')} ms engine)")
            return 0
        print("  JSON without png:", json.dumps(body)[:300])
        return 1
    print("  unexpected content-type", ctype, len(raw))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
