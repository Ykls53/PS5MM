#!/usr/bin/env python3
"""方案 B（最小验证版）：每句之前先把上一次的图彻底放掉。

实测（PC，连打 5 次）：5.3s -> 74.8s -> 83.5s -> 96.0s -> 98.1s

怀疑是 ggml 的 compute buffer 反复 allocate 越来越碎：llama_memory_clear 只清
KV，不清「上一次 decode 建的临时图」。llama_synchronize 会等图跑完并把中间
buffer 还给 allocator。

先只加一句 llama_synchronize（放在 memory_clear 后面），成本几乎为零，
在 PC 上跑重复测试看曲线有没有变平。

    python3 patch-tts-sync.py [--check|--revert]
"""
import sys
from pathlib import Path

T = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")

OLD = """    // The last request's tokens must go, or this one continues its sentence.
    llama_memory_clear(llama_get_memory(g_e.lctx), true);
"""

NEW = """    // The last request's tokens must go, or this one continues its sentence.
    llama_memory_clear(llama_get_memory(g_e.lctx), true);
    // 上一句的临时图可能还挂在 allocator 上：清完 KV 再同步一次，
    // 让 ggml 把这一轮算完的中间 buffer 还回去。实测第二句开始慢 14 倍，
    // 怀疑就是这里没释放干净。
    llama_synchronize(g_e.lctx);
"""


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = T.read_text(encoding="utf-8")
    if mode == "--check":
        print(f"old={src.count(OLD)} new={src.count(NEW)}")
        return 0
    if mode == "--revert":
        if NEW in src:
            T.write_text(src.replace(NEW, OLD, 1), encoding="utf-8")
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
    T.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched: llama_synchronize after memory_clear")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
