#!/usr/bin/env python3
"""Image -> video -> image, on one process, without restarting anything.

This is the regression test for the model-slot bug: once the video set (Wan) is
loaded, a later txt2img used to run on Wan's DiT and come out broken. Now the
engine unloads the other set and reloads the right one.
"""
import base64
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8002"


def post(path, body, timeout=3600):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"  HTTP {e.code}: {body[:300]}")
        return None, time.time() - t0
    return (raw, ctype), time.time() - t0


def health():
    with urllib.request.urlopen(BASE + "/health", timeout=30) as r:
        return json.loads(r.read())


def step_image(tag, out):
    body = {"prompt": "a white whale girl, flat illustration, soft light",
            "steps": 2, "width": 256, "height": 256, "cfg_scale": 5.0}
    res, dt = post("/sdapi/v1/txt2img", body)
    if res is None:
        return False
    raw, _ = res
    data = json.loads(raw)["images"][0]
    blob = base64.b64decode(data.split(",", 1)[1] if data.startswith("data:") else data)
    with open(out, "wb") as f:
        f.write(blob)
    h = health()
    print(f"[{tag}] OK {dt:.1f}s png={len(blob)}B loaded={h['model_loaded']} model={h['model'].split('/')[-1]}")
    return True


def step_video(tag, out):
    body = {"prompt": "a white whale swimming in a calm blue ocean",
            "frames": 5, "width": 320, "height": 192, "steps": 2, "fps": 8, "flow_shift": 3.0}
    res, dt = post("/sdapi/v1/txt2vid", body)
    if res is None:
        return False
    raw, ctype = res
    with open(out, "wb") as f:
        f.write(raw)
    h = health()
    ok = raw[:4] == b"RIFF"
    print(f"[{tag}] {'OK' if ok else 'BAD'} {dt:.1f}s {ctype} {len(raw)}B riff={ok} "
          f"loaded={h['model_loaded']} model={h['model'].split('/')[-1]}")
    return ok


def main():
    ok = True
    ok &= step_image("image-1", "/tmp/host-slot-1.png")
    ok &= step_video("video-1", "/tmp/host-slot-1.avi")
    ok &= step_image("image-2-after-video", "/tmp/host-slot-2.png")
    ok &= step_video("video-2-again", "/tmp/host-slot-2.avi")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
