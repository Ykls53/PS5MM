#!/usr/bin/env python3
"""Add a PS5MM_TTS_NGL knob to tts_server.cpp.

Why: the speech engine hard-codes n_gpu_layers = 999 ("the APU shares one pool,
all of it sits on the GPU"), which is right on the console. On a PC the same
line makes llama.cpp abort inside llama_model_load_from_file (ggml-alloc: not
enough space in the buffer), and an abort takes the whole app with it -- so the
host build has no way to load the speech model at all.

Default stays 999, so console behaviour is unchanged.

    python3 patch-tts-ngl.py            apply
    python3 patch-tts-ngl.py --check    report
    python3 patch-tts-ngl.py --revert   undo
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")

OLD = """    mparams.n_gpu_layers       = 999;   // the APU shares one pool: all of it sits on the GPU
"""
NEW = """    mparams.n_gpu_layers       = 999;   // the APU shares one pool: all of it sits on the GPU
    // Escape hatch for machines with no Vulkan device (the PC verification
    // build): 999 there makes llama.cpp abort inside the model loader.
    if (const char * ngl = std::getenv("PS5MM_TTS_NGL"); ngl != nullptr && ngl[0] != 0) {
        mparams.n_gpu_layers = std::atoi(ngl);
    }
"""


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = TARGET.read_text(encoding="utf-8")
    has_new = NEW in src
    has_old = src.count(OLD) == 1

    if mode == "--check":
        print(f"applied={has_new} old_present={has_old}")
        return 0
    if mode == "--revert":
        if has_new:
            TARGET.write_text(src.replace(NEW, OLD), encoding="utf-8")
            print("reverted")
        else:
            print("nothing to revert")
        return 0
    if has_new:
        print("already applied")
        return 0
    if not has_old:
        print("anchor not found exactly once; refusing", file=sys.stderr)
        return 2
    TARGET.write_text(src.replace(OLD, NEW), encoding="utf-8")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
