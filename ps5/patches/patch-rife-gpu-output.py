#!/usr/bin/env python3
"""Same null-output bug on the GPU paths.

process() and process_v4() build a Mat on top of outimage.data before anything
has allocated outimage:

    out = ncnn::Mat(out_gpu.w, out_gpu.h, (unsigned char*) outimage.data, (size_t) channels, 1);

With gpuid = -1 the CPU paths run and this never executes, but the moment RIFE
is given a GPU device (gpuid >= 0) those two entry points hand ncnn a null
buffer. Allocating the caller's Mat first makes the GPU path correct instead of
latent. The CPU paths are untouched (already fixed by patch-rife-cpu-output.py).

    python3 patch-rife-gpu-output.py [--check|--revert]
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/ext/rife-ncnn/src/rife.cpp")

OLD = """            out = ncnn::Mat(out_gpu.w, out_gpu.h, (unsigned char*)outimage.data, (size_t)channels, 1);"""

NEW = """            // PS5MM: the caller's Mat arrives empty; give it storage before
            // wrapping it (a null outimage.data segfaults on the first write).
            if (outimage.data == nullptr || outimage.w != out_gpu.w || outimage.h != out_gpu.h) {
                outimage.create(out_gpu.w, out_gpu.h, channels, (size_t) 1, nullptr);
            }
            out = ncnn::Mat(out_gpu.w, out_gpu.h, (unsigned char*)outimage.data, (size_t)channels, 1);"""


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = TARGET.read_text(encoding="utf-8")
    n_old = src.count(OLD)
    n_new = src.count(NEW)
    if mode == "--check":
        print(f"old={n_old} patched={n_new}")
        return 0
    if mode == "--revert":
        if n_new:
            TARGET.write_text(src.replace(NEW, OLD), encoding="utf-8")
            print(f"reverted {n_new}")
        else:
            print("nothing to revert")
        return 0
    if n_old == 0:
        print("already patched" if n_new else "anchor not found", file=sys.stderr)
        return 0 if n_new else 2
    TARGET.write_text(src.replace(OLD, NEW), encoding="utf-8")
    print(f"patched {n_old} GPU entry point(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
