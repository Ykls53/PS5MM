#!/usr/bin/env python3
"""Make the speech engine's n_gpu_layers honest instead of hard-coded 999.

The line is right for the console ("the APU shares one pool, all of it sits on
the GPU"), but on a build with no GPU backend llama.cpp still *believes* it must
place 999 layers on a GPU: it sizes buffers for a device that does not exist and
aborts inside the model loader --

    ggml-alloc.c:83: not enough space in the buffer
    llama_model_base::load_tensors -> ggml_tallocr_alloc -> ggml_abort

...which takes the whole app with it (SIGABRT, every engine gone).

Fix: ask ggml whether a GPU backend exists at all. PS5 has RADV, so the console
keeps 999 and nothing changes there. The PS5MM_TTS_NGL knob stays for override.

    python3 patch-tts-ngl-auto.py [--check|--revert]
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")

OLD_INC = """#include "llama.h"
#include "mtmd.h"
#include "mtmd-helper.h"
"""
NEW_INC = """#include "llama.h"
#include "mtmd.h"
#include "mtmd-helper.h"

#include "ggml-backend.h"   // ggml_backend_dev_by_type(): is there a GPU at all?
"""

OLD = """    mparams.n_gpu_layers       = 999;   // the APU shares one pool: all of it sits on the GPU
    // Escape hatch for machines with no Vulkan device (the PC verification
    // build): 999 there makes llama.cpp abort inside the model loader.
    if (const char * ngl = std::getenv("PS5MM_TTS_NGL"); ngl != nullptr && ngl[0] != 0) {
        mparams.n_gpu_layers = std::atoi(ngl);
    }
"""

NEW = """    mparams.n_gpu_layers       = 999;   // the APU shares one pool: all of it sits on the GPU
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
    std::printf("ps5mm-tts: n_gpu_layers = %d\\n", (int) mparams.n_gpu_layers);
    std::fflush(nullptr);
"""

EDITS = [(OLD_INC, NEW_INC, "include"), (OLD, NEW, "auto ngl")]


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--check":
        src = TARGET.read_text(encoding="utf-8")
        for old, new, tag in EDITS:
            print(f"{'applied' if new in src else ('todo' if old in src else 'MISSING'):8s} {tag}")
        return 0
    if mode == "--revert":
        src = TARGET.read_text(encoding="utf-8")
        for old, new, tag in reversed(EDITS):
            src = src.replace(new, old, 1)
        TARGET.write_text(src, encoding="utf-8")
        print("reverted")
        return 0
    failed = False
    for old, new, tag in EDITS:
        src = TARGET.read_text(encoding="utf-8")
        if new in src:
            print(f"skip     {tag}")
            continue
        if src.count(old) != 1:
            print(f"FAILED   {tag}: anchor x{src.count(old)}", file=sys.stderr)
            failed = True
            continue
        TARGET.write_text(src.replace(old, new, 1), encoding="utf-8")
        print(f"patched  {tag}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
