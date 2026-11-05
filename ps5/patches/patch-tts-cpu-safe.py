#!/usr/bin/env python3
"""Speech must not run on the GPU: it locks the whole process on RADV.

Measured 2026-11-05 on the console: one /v1/audio/speech request, and then
8002 / 8004 / 8005 / 8099 all time out over HTTP while TCP stays listening --
the main loop is stuck too, so even /data/PS5MM/quit is never read. The log stops
right after `init_audio: audio input is in experimental stage`.

The culprit is the mtmd audio path (qwen3tts_gen projector) on RADV. Until that
is fixed upstream, speech runs on the CPU: 1.7B Q4 on 8 cores is tens of
seconds per sentence -- slow, but it cannot wedge the app. PS5MM_TTS_NGL still
overrides for experiments.

    python3 patch-tts-cpu-safe.py [--check|--revert]
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")

OLD = """    mparams.n_gpu_layers       = 999;   // the APU shares one pool: all of it sits on the GPU
    // A build without a GPU backend must not claim GPU layers: llama.cpp would
    // size the buffers for a device that is not there and ggml_abort() inside
    // llama_model_load_from_file -- which kills this process, not just speech.
    // PS5 always has RADV here, so the console behaviour is unchanged.
    if (ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_GPU) == nullptr) {
        mparams.n_gpu_layers = 0;
    }
    if (const char * ngl = std::getenv("PS5MM_TTS_NGL"); ngl != nullptr && ngl[0] != 0) {
        mparams.n_gpu_layers = std::atoi(ngl);
    }
"""

NEW = """    // 语音跑 CPU，不上 GPU。
    // 2026-11-05 实测：在 RADV 上跑 mtmd 的音频生成（qwen3tts_gen 投影器）会把
    // 整个进程锁死 —— 一句话的请求发出去之后，8002 / 8004 / 8005 / 8099 全部
    // HTTP 超时（TCP 还在听），主循环也停住，连 /data/PS5MM/quit 都读不到，
    // 只能长按电源。log 停在 init_audio 那一行。
    // 一句 1.7B Q4 的话在 8 核上是几十秒的量级：慢，但不会把 app 拖死。
    // 上游修好之前别开 GPU；要试验时用 PS5MM_TTS_NGL 覆盖。
    mparams.n_gpu_layers = 0;
    if (const char * ngl = std::getenv("PS5MM_TTS_NGL"); ngl != nullptr && ngl[0] != 0) {
        mparams.n_gpu_layers = std::atoi(ngl);
    }
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
    print("patched: speech pinned to CPU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
