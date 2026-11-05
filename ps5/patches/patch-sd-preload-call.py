#!/usr/bin/env python3
"""Finish the model-set patch: sd_server_preload still calls ensure_ctx(err).

ensure_ctx gained a bool ("is this the video set?"), so the preload call has to
say which set it wants. Preloading means the image set: that is what "load the
picture model at boot" asks for. Video still loads lazily on the first txt2vid.

    python3 patch-sd-preload-call.py [--check|--revert]
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/PS5MM/ps5/app/sd_server.cpp")
OLD = "    if (!ensure_ctx(err)) {"
NEW = "    if (!ensure_ctx(false, err)) {   // 预加载的是图片那套，视频等第一次出片"


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = TARGET.read_text(encoding="utf-8")
    if mode == "--check":
        print(f"old={src.count(OLD)} new={src.count(NEW)}")
        return 0
    if mode == "--revert":
        if NEW in src:
            TARGET.write_text(src.replace(NEW, OLD, 1), encoding="utf-8")
            print("reverted")
        else:
            print("nothing to revert")
        return 0
    n = src.count(OLD)
    if n == 0:
        print("already applied" if NEW in src else "anchor not found", file=sys.stderr)
        return 0 if NEW in src else 2
    if n != 1:
        print(f"anchor found {n} times; refusing", file=sys.stderr)
        return 2
    TARGET.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched preload call")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
