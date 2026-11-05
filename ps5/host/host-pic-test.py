#!/usr/bin/env python3
"""Smoke test for the host build's picture engine: txt2img -> PNG on disk."""
import base64
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8002"


def post(path, body, timeout=1800):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw), time.time() - t0


def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "a white whale girl, flat illustration, soft light"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 256
    out = sys.argv[4] if len(sys.argv) > 4 else "/tmp/host-pic.png"
    body = {"prompt": prompt, "steps": steps, "width": size, "height": size, "cfg_scale": 5.0}
    try:
        res, dt = post("/sdapi/v1/txt2img", body)
    except Exception as e:  # noqa: BLE001
        print("FAIL", type(e).__name__, e)
        return 1
    imgs = res.get("images") or []
    print(f"OK elapsed={dt:.2f}s images={len(imgs)}")
    if not imgs:
        print("no image in response:", json.dumps(res)[:400])
        return 2
    data = imgs[0]
    if "," in data and data.startswith("data:"):
        data = data.split(",", 1)[1]
    blob = base64.b64decode(data)
    with open(out, "wb") as f:
        f.write(blob)
    print(f"saved {out} ({len(blob)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
