#!/usr/bin/env python3
"""删掉 flash_attn 那行，让 tts 回到备份 eboot 的状态。

证据链：
  备份 eboot（338,837,736，能跑，2.4s 出音频）用的是 llama 默认值 —— log 里
  明写 "warmup: flash attention is enabled"。
  我编的版本加了 cparams.flash_attn_type = DISABLED，然后卡死。
  除此之外 tts_server.cpp 和备份版的差别只有 printf 和「无 GPU 就降 0」的检测，
  在 PS5 上都不改变行为（有 RADV -> 仍是 999）。

关掉 flash attention 会切到另一条 attention 实现（mul_mat 路径），那条在 RADV 上
可能就是卡住的那条。所以：删掉，回默认。

    python3 revert-tts-flashattn.py [--check|--revert]
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")

OLD = """    // RADV 上 flash attention 有前科：sd_server 那边 flash_attn=true 会 load 失败，
    // 要关掉重试。tts 这一侧从没设过这个字段，用的是默认值，日志里明写
    // "warmup: flash attention is enabled"，而三次都卡在这之后。
    cparams.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED;
"""
NEW = ""


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = TARGET.read_text(encoding="utf-8")
    if mode == "--check":
        print(f"old={src.count(OLD)} flash_attn_lines={src.count('flash_attn')}")
        return 0
    if mode == "--revert":
        if OLD not in src:
            print("nothing to revert (already at default)")
            return 0
        print("re-adding is not needed; flash_attn is already removed")
        return 0
    if OLD not in src:
        print("already removed")
        return 0
    if src.count(OLD) != 1:
        print(f"anchor x{src.count(OLD)}; refusing", file=sys.stderr)
        return 2
    TARGET.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("removed: flash_attn back to llama default")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
