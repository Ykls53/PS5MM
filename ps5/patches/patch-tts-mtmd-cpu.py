#!/usr/bin/env python3
"""mtmd's projector must stay on the CPU too.

Setting n_gpu_layers = 0 only moved the talker model; the mmproj (the audio
projector) still opened a Vulkan context (`clip_ctx: CLIP using Vulkan0
backend`) and the first synthesis request wedged the whole process -- the same
lock-up as before, with the talker already on CPU.

`mp.use_gpu` is the switch for that half. With both halves on the CPU the speech
engine cannot touch RADV at all: tens of seconds per sentence, but it can no
longer take the app down.

    python3 patch-tts-mtmd-cpu.py [--check|--revert]
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")

OLD = """    mtmd_context_params mp = mtmd_context_params_default();
    mp.use_gpu             = true;
"""
NEW = """    mtmd_context_params mp = mtmd_context_params_default();
    // 投影器也不能上 GPU：只把主模型放 CPU 不够，第一次合成照样把整个进程锁死
    // （日志 clip_ctx: CLIP using Vulkan0 backend 之后 8002/8004/8005/8099 全超时）。
    mp.use_gpu             = false;
"""


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
    print("patched: mtmd projector on CPU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
