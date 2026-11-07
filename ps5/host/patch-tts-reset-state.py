#!/usr/bin/env python3
"""方案 B：每句合成完，把 per-generation 状态彻底清干净。

实测数据（PC，连打 5 次）：
  #1  5,293 ms  ← 第一发永远快
  #2 74,783 ms  ← 之后 14 倍
  #3 83,483 ms
  #4 95,952 ms
  #5 98,086 ms

根因线索（mtmd-helper-gen.cpp）：
  reset() 清了 9 个成员，但 tok_embd（整个词表嵌入矩阵）没在清，
  ensure_cache() 里每次 set_input 都会 resize + 全量拷。
  而且 llama context 的 compute buffer 反复 allocate 会越来越碎。

B 的做法（便宜、不用重建 context）：
  1. synthesize() 结尾：llama_memory_clear + 把 gen 对象销毁（作用域结束就行）
  2. 每 N 句（默认 1）主动调一次 llama_synchronize，把图释放掉
  3. 关键：在 gen 销毁后，调 llama_memory_clear 两次（清 seq + 清 defrag）

    python3 patch-tts-reset-state.py [--check|--revert]
"""
import sys
from pathlib import Path

T = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")

OLD = """    wav.assign(data, len);
    std::printf("ps5mm-tts: %d frames, %d Hz, %zu bytes of wav in %lld ms\\n", frames, rate, len,
                (long long) (ggml_time_ms() - t0));
    std::fflush(nullptr);
    return true;
}"""

NEW = """    wav.assign(data, len);
    std::printf("ps5mm-tts: %d frames, %d Hz, %zu bytes of wav in %lld ms\\n", frames, rate, len,
                (long long) (ggml_time_ms() - t0));

    // 把这次生成留下的东西彻底放掉，下一句才不会被拖慢。
    // 实测（PC）：不清的话第二句开始慢 14 倍，第五句 98 秒。
    // gen 是在上面那个作用域里构造的，这里它已经析构；剩下的 KV / compute buffer
    // 要显式清 + 同步一次，让 ggml 把临时图还给 allocator。
    (void) gen.get_output(&rate, &data, &len, &n);   // 幂等，只为确认 gen 还活着
    llama_memory_clear(llama_get_memory(g_e.lctx), true);
    llama_synchronize(g_e.lctx);
    llama_memory_clear(llama_get_memory(g_e.lctx), true);
    std::fflush(nullptr);
    return true;
}"""


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
    print("patched: clear state after each synthesis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
