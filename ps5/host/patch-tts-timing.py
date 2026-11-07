#!/usr/bin/env python3
"""给 synthesize 加分段计时，看那 80 秒到底花在哪一段。

不猜了：把 set_input / step_prompt / 逐帧 step_gen 各自计时打出来。
第一次和第二次对比，就知道是 prefill 变慢还是逐帧变慢。

    python3 patch-tts-timing.py [--check|--revert]
"""
import sys
from pathlib import Path

T = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")
EDITS = []


def edit(old, new, tag):
    EDITS.append((old, new, tag))


# 1. set_input + step_prompt 计时
edit(
    """    const int64_t t0 = ggml_time_ms();
    if (gen.set_input(&inp) != 0) {
        err = "the prompt was refused";
        return false;
    }
    for (;;) {
        const int32_t left = gen.step_prompt(kPromptBatch);
        if (left < 0) {
            err = "prompt processing failed";
            return false;
        }
        if (left == 0) {
            break;
        }
    }""",
    """    const int64_t t0 = ggml_time_ms();
    if (gen.set_input(&inp) != 0) {
        err = "the prompt was refused";
        return false;
    }
    const int64_t t_input = ggml_time_ms();
    int           prefill_rounds = 0;
    for (;;) {
        const int32_t left = gen.step_prompt(kPromptBatch);
        if (left < 0) {
            err = "prompt processing failed";
            return false;
        }
        prefill_rounds++;
        if (left == 0) {
            break;
        }
    }
    const int64_t t_prefill = ggml_time_ms();
    std::printf("ps5mm-tts: set_input %lld ms, prefill %lld ms (%d rounds)\\n",
                (long long) (t_input - t0), (long long) (t_prefill - t_input), prefill_rounds);
    std::fflush(nullptr);""",
    "timing: input + prefill",
)

# 2. 逐帧计时（每 10 帧报一次）
edit(
    """    while (!stop && frames < kMaxFrames) {
        const float * h_next = nullptr;
        if (gen.step_gen(sampled, h, &h_next, &stop) != 0) {
            llama_sampler_free(smpl);
            err = "generation failed";
            return false;
        }
        if (h_next == nullptr) {
            break;   // stopped without a frame
        }
        frames++;
        h       = h_next;
        sampled = llama_sampler_sample(smpl, g_e.lctx, -1);
    }
    llama_sampler_free(smpl);""",
    """    int64_t t_gen = ggml_time_ms();
    while (!stop && frames < kMaxFrames) {
        const float * h_next = nullptr;
        if (gen.step_gen(sampled, h, &h_next, &stop) != 0) {
            llama_sampler_free(smpl);
            err = "generation failed";
            return false;
        }
        if (h_next == nullptr) {
            break;   // stopped without a frame
        }
        frames++;
        if (frames % 10 == 0) {
            const int64_t now = ggml_time_ms();
            std::printf("ps5mm-tts:   frame %d, avg %.0f ms/frame\\n", frames,
                        (double) (now - t_gen) / 10.0);
            std::fflush(nullptr);
            t_gen = now;
        }
        h       = h_next;
        sampled = llama_sampler_sample(smpl, g_e.lctx, -1);
    }
    llama_sampler_free(smpl);""",
    "timing: per-frame",
)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = T.read_text(encoding="utf-8")
    if mode == "--check":
        for old, new, tag in EDITS:
            print(f"{'applied' if new in src else ('todo' if old in src else 'MISSING'):8s} {tag}")
        return 0
    if mode == "--revert":
        for old, new, tag in reversed(EDITS):
            if new in src:
                src = src.replace(new, old, 1)
        T.write_text(src, encoding="utf-8")
        print("reverted")
        return 0
    failed = False
    for old, new, tag in EDITS:
        if new in src:
            print(f"skip     {tag}")
            continue
        if src.count(old) != 1:
            print(f"FAILED   {tag}: anchor x{src.count(old)}", file=sys.stderr)
            failed = True
            continue
        src = src.replace(old, new, 1)
        print(f"patched  {tag}")
    T.write_text(src, encoding="utf-8")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
