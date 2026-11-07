#!/usr/bin/env python3
"""每句重建 mtmd_context（投影器），这是最后一个没试过的方向。

依据：
  flush_gen_wav() 把 c2w_state 写回、下一句继续用（流式状态）。
  reset() 里 c2w_state.clear() 只是清本地那份拷贝；
  mtmd_gen_audio_process(mctx, ...) 很可能往 mctx 内部塞了解码器状态，
  而 mctx 整个进程只 init 一次（tts_server.cpp:378），从不重建。

试过无效的：llama_synchronize / seq_rm / 整个 llama_context 重建。
所以嫌疑落到 mctx 上。

    python3 patch-tts-rebuild-mctx.py [--check|--revert]
"""
import sys
from pathlib import Path

T = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")

OLD = """    // 每句前重建 context。
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

NEW = """    // 每句前重建 mtmd 投影器上下文。
    // 实测（PC，分段计时）：第一句 63ms/帧，之后恒定 1817ms/帧（29 倍）。
    // 已经排除的：llama_memory_clear / seq_rm / synchronize / 整个 llama_context
    // 重建 —— 四种都没用，说明降级状态不在 llama 那边。
    // 剩下的嫌疑：mtmd_gen_audio_process(mctx) 往 mctx 内部塞了解码器状态
    // （flush_gen_wav 里 c2w_state 只是被返回的一份拷贝，mctx 里那份没清过）。
    // 投影器只有 425 MB，重建比重建主模型便宜。
    if (g_e.mctx != nullptr) {
        mtmd_free(g_e.mctx);
        g_e.mctx = nullptr;
    }
    {
        mtmd_context_params mp = mtmd_context_params_default();
        mp.use_gpu             = true;
        mp.print_timings       = false;
        mp.n_threads           = (int) std::thread::hardware_concurrency();
        g_e.mctx               = mtmd_init_from_file(g_e.mmproj.c_str(), g_e.model, mp);
        if (g_e.mctx == nullptr) {
            err = "could not rebuild the audio projector";
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
    print("patched: rebuild mtmd context before each synthesis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
