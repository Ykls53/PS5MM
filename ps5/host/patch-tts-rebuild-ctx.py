#!/usr/bin/env python3
"""方案 A：每句合成前把 llama_context 销毁重建。

依据（PC 实测，加分段计时）：
  prefill:   88 ms   -> 303 ms      （3 倍）
  set_input: 847 ms  -> 483 ms      （反而快）
  逐帧生成:   63 ms/frame -> 1817 ms/frame  （29 倍）  ← 全在这

试过两种清理都无效：
  - llama_synchronize            -> 无效
  - llama_memory_seq_rm + clear  -> 无效

说明不是 KV 残留，是 context 自身的某种状态（compute buffer / graph cache）
进了降级路径。既然清不掉，就整个换新的 —— 权重还在（llama_model 是独立的），
只需重跑 llama_init_from_model，代价几秒，换来每句都走「第一次」那条快路。

    python3 patch-tts-rebuild-ctx.py [--check|--revert]
"""
import sys
from pathlib import Path

T = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")

OLD = """    // 上一句的 KV 必须真正删掉，不能只 clear。
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

NEW = """    // 每句前重建 context。
    // 实测（PC）：第一句 63ms/帧，之后 1817ms/帧（慢 29 倍）。
    // llama_memory_clear / seq_rm / synchronize 三种清法都没用 —— 说明降级的
    // 是 context 自己的状态，不是 KV。既然清不掉就换个新的：
    // 权重（g_e.model）是独立的，重跑 llama_init_from_model 只要几秒，
    // 换来每句都走「第一句」那条快路。
    if (g_e.lctx != nullptr) {
        llama_free(g_e.lctx);
        g_e.lctx = nullptr;
    }
    {
        llama_context_params cparams = llama_context_default_params();
        const unsigned     hw        = std::thread::hardware_concurrency();
        cparams.n_ctx      = 4096;
        cparams.n_batch    = kPromptBatch;
        cparams.n_ubatch   = 256;
        cparams.n_threads  = hw > 4 ? (int) (hw - 2) : 4;
        cparams.embeddings = true;
        cparams.no_perf    = true;
        g_e.lctx           = llama_init_from_model(g_e.model, cparams);
        if (g_e.lctx == nullptr) {
            err = "could not rebuild the speech context";
            return false;
        }
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
    print("patched: rebuild context before each synthesis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
