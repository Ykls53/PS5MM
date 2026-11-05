#!/usr/bin/env python3
"""Turn mmap off for the picture engine's weights.

On the console the load stops right after `using mmap for I/O` and never
finishes: no tensor log lines, watchdog fires at 300 s. Whether that is drvfs
semantics, the UFS mount or the RADV upload path, reading the file normally is
the cheaper thing to try first -- 3 GB through read() is seconds, and the pool is
the same either way.

    python3 patch-sd-nommap.py [--check|--revert]
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/PS5MM/ps5/app/sd_server.cpp")

OLD = """    cp.n_threads   = ps5mm::caps().threads;
    cp.enable_mmap = true;"""

NEW = """    cp.n_threads   = ps5mm::caps().threads;
    // 不要在 /data 上走 mmap：实测（2026-11-05）加载停在 "using mmap for I/O"
    // 之后就再没有张量日志，300 秒看门狗放弃。改成普通读，3 GB 几秒读完，
    // 内存池的占用还是一样。
    cp.enable_mmap = false;"""


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
    if NEW in src:
        print("already applied")
        return 0
    if src.count(OLD) != 1:
        print(f"anchor x{src.count(OLD)}; refusing", file=sys.stderr)
        return 2
    TARGET.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched: enable_mmap = false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
