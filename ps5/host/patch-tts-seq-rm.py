#!/usr/bin/env python3
"""每句开头按 seq 真删 KV，而不是只 clear。

实测（PC，连打 5 次，加了分段计时）：
  prefill:  88 ms  ->  303 ms        只慢 3 倍
  set_input: 847 ms ->  483 ms       反而快了
  逐帧生成:  63 ms/frame -> 1817 ms/frame   慢 29 倍  ← 全在这

每帧只做一件事：llama_decode + code2wav。prefill 走同一套代码却正常，
说明不是「模型变慢」，是「逐帧那条路的状态没被重置」。

llama_memory_clear(mem, true) 只是把 seq 标记为空，图还在。
gen 用的是 seq_id = 0，从没被 seq_rm 过 -> 每句的 KV 都堆在同一个 seq 上。

改成：每句开头 llama_memory_seq_rm(mem, 0, -1, -1) 真删，然后再 clear 一次兜底。

    python3 patch-tts-seq-rm.py [--check|--revert]
"""
import sys
from pathlib import Path

T = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")

OLD = """    // The last request's tokens must go, or this one continues its sentence.
    llama_memory_clear(llama_get_memory(g_e.lctx), true);
    // 上一句的临时图可能还挂在 allocator 上：清完 KV 再同步一次，
    // 让 ggml 把这一轮算完的中间 buffer 还回去。实测第二句开始慢 14 倍，
    // 怀疑就是这里没释放干净。
    llama_synchronize(g_e.lctx);
"""

NEW = """    // 上一句的 KV 必须真正删掉，不能只 clear。
    // 实测：clear() 之后 prefill 只慢 3 倍，但逐帧生成从 63ms/帧 变成 1817ms/帧
    // （慢 29 倍）—— 说明 KV 只是被标空，逐帧那条路还在啃一坨没释放的图。
    // gen 用的是 seq_id = 0，所以按 seq 真删。
    {
        llama_memory_t mem = llama_get_memory(g_e.lctx);
        (void) llama_memory_seq_rm(mem, 0, -1, -1);   // 删掉 seq 0 的全部 KV
        llama_memory_clear(mem, true);                 // 兜底：其余 seq 也标空
        llama_synchronize(g_e.lctx);
    }
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
    print("patched: seq_rm before each synthesis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
