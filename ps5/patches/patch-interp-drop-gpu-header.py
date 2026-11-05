#!/usr/bin/env python3
"""去掉 interp_server.cpp 里那个已经用不到的 ncnn GPU 头。

为什么可能是它：ncnn 的 Vulkan 初始化会调 glslang::InitializeProcess()，
而 llama 的 Vulkan 后端用同一套 SPIR-V 工具链。这是新旧版本唯一会动
GPU 全局状态的差异。插帧已经钉死 gpuid=-1（CPU），本来就不需要这个头。

保守做法：只删 include，不动任何逻辑。如果编译不过，说明 rife.h 间接需要它，
那时再补回来。

    python3 patch-interp-drop-gpu-header.py [--check|--revert]
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/PS5MM/ps5/app/interp_server.cpp")

OLD = '#include "gpu.h"      // ncnn::get_gpu_count / get_gpu_info\n'
NEW = ('// 不需要 ncnn 的 GPU 头：gpuid 已经钉死 -1，走纯 CPU。\n'
       '// 留着它会拖进 ncnn 的 Vulkan，初始化时调 glslang::InitializeProcess()，\n'
       '// 和 llama 的 Vulkan 后端共用同一套 SPIR-V 工具链 —— 疑似破坏语音的那一处。\n')


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
    print("patched: dropped ncnn gpu header")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
