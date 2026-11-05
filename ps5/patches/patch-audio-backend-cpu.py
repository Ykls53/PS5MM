#!/usr/bin/env python3
"""audio.cpp defaults to the CPU backend.

Why: with `backend = "vulkan"` the first synthesis never returns on the console
(the session create / backend init wedges on RADV), while the same model on the
CPU runs at rtf ≈ 1.1 -- a sentence in a few seconds. So CPU is the right
default here; the GPU path stays available through PS5MM_AUDIO_BACKEND for
experiments.

    python3 patch-audio-backend-cpu.py [--check|--revert]
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/PS5MM/ps5/app/audio_server.cpp")

OLD = """    // backend_config = nullptr 在 audio.cpp 里就是「用 CPU」。PS5 上跑 TTS
    // 必须显式要 Vulkan，否则一句话要好几分钟。没有 Vulkan 的构建（PC 验证）
    // 会创建失败，那时才退回默认。
    audiocpp_backend_config be{};
    be.backend = "vulkan";
    be.device  = 0;
    be.threads = 0;"""

NEW = """    // 默认走 CPU。实测（2026-11-05）：backend = "vulkan" 时第一次合成就再也不返回
    // （RADV 上的 session/backend 初始化卡住），而同一份模型在 CPU 上 rtf ≈ 1.1，
    // 一句话几秒钟。想试 GPU 就把 PS5MM_AUDIO_BACKEND=vulkan 设上。
    const char * want_backend = std::getenv("PS5MM_AUDIO_BACKEND");
    audiocpp_backend_config be{};
    be.backend = (want_backend != nullptr && want_backend[0] != 0) ? want_backend : "cpu";
    be.device  = 0;
    be.threads = 0;"""


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
    print("patched: audio backend defaults to cpu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
