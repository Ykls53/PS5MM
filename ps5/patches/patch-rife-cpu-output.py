#!/usr/bin/env python3
"""Fix the RIFE CPU path: every process_*_cpu() wrote into an empty Mat.

All four CPU entry points end with

    out.create(w, h, 3);          // `out` is a local
    ...
#if _WIN32
    out.to_pixels((unsigned char*) outimage.data, PIXEL_RGB2BGR);
#else
    out.to_pixels((unsigned char*) outimage.data, PIXEL_RGB);
#endif

`outimage` is the caller's output Mat and it arrives empty, so `outimage.data`
is nullptr and the first pixel write segfaults -- that is the SIGSEGV that kept
frame interpolation off. The GPU paths never hit it because they render into
outimage directly.

Handing the whole Mat back keeps the float 0..255 pixels ncnn produced and lets
the caller convert (interp_server already does exactly that in encode_png).

    python3 patch-rife-cpu-output.py [--check|--revert]
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/ext/rife-ncnn/src/rife.cpp")

OLD = """    // download
    {
#if _WIN32
        out.to_pixels((unsigned char*)outimage.data, ncnn::Mat::PIXEL_RGB2BGR);
#else
        out.to_pixels((unsigned char*)outimage.data, ncnn::Mat::PIXEL_RGB);
#endif
    }
"""

NEW = """    // download
    //
    // PS5MM: hand the whole Mat back instead of writing into outimage.data.
    // outimage arrives empty and `out` is a local, so to_pixels() was given a
    // null buffer -- every CPU-path interpolation died with SIGSEGV there.
    // The pixels stay float 0..255; the caller converts (encode_png does).
    outimage = out;
"""


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = TARGET.read_text(encoding="utf-8")
    n_old = src.count(OLD)
    n_new = src.count(NEW)
    if mode == "--check":
        print(f"old_blocks={n_old} patched_blocks={n_new}")
        return 0
    if mode == "--revert":
        if n_new:
            TARGET.write_text(src.replace(NEW, OLD), encoding="utf-8")
            print(f"reverted {n_new} block(s)")
        else:
            print("nothing to revert")
        return 0
    if n_old == 0:
        print("already patched" if n_new else "anchor not found", file=sys.stderr)
        return 0 if n_new else 2
    TARGET.write_text(src.replace(OLD, NEW), encoding="utf-8")
    print(f"patched {n_old} CPU entry point(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
