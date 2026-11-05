#!/usr/bin/env python3
"""Two engines that were quietly pinned to the CPU. The console's CPU is a Zen 2
part with no matrix units -- an engine that runs there instead of on the GPU is
not "slower", it is unusable.

1. RIFE (interp_server.cpp) was hard-wired to `new RIFE(-1, ...)`: vkdev = null,
   every process() call takes the CPU path. That was a workaround for a SIGSEGV
   we have since found and fixed (an unallocated output Mat in the CPU path), so
   the pin can go. New rule: use GPU device 0 when ncnn reports a *hardware*
   one; fall back to CPU only when there is nothing or only llvmpipe (the WSL
   software renderer, which is slower than the CPU path).

2. audio (audio_server.cpp) passed backend_config = nullptr, and the C API
   documents exactly that as "cpu". TTS on 8 Zen 2 cores is minutes per
   sentence, so ask for Vulkan first and only fall back when the session cannot
   be created (the PC build has no Vulkan backend for audio.cpp).

    python3 patch-gpu-first.py [--check|--revert]
"""
import sys
from pathlib import Path

APP = Path("/home/yk/PS5MM/ps5/app")
EDITS = []


def edit(path, old, new, tag):
    EDITS.append((path, old, new, tag))


edit(
    APP / "interp_server.cpp",
    """    // gpuid = -1 keeps vkdev = nullptr, so every process() call takes the CPU
    // path (rife.cpp:381 -> process_v4_cpu / process_cpu). The old 0 called
    // ncnn::get_gpu_device(0), which SIGSEGVs on this machine before load()
    // can even return an error code -- that is why interp had to stay off.
    // Cost: CPU is slower per frame, but it actually runs.
    auto * r = new RIFE(-1, false, false, uhd, threads, v2, v4);""",
    """    // CPU 是最后手段，不是默认：PS5 的 CPU 是 8 核 Zen 2，一帧插值要好几秒。
    // 之前写死 -1 是为了绕开一个 SIGSEGV，而那个 SIGSEGV 的真身已经找到并修掉了
    // （CPU 路径往没分配过的 outimage.data 里写像素），所以这里恢复成「有硬件
    // GPU 就走 GPU」。
    // llvmpipe 是 Mesa 的软件 Vulkan（WSL 上就有），拿它当 GPU 比 CPU 还慢，
    // 所以按名字排掉。
    int gpuid = -1;
    if (ncnn::get_gpu_count() > 0) {
        const char * dev = ncnn::get_gpu_info(0).device_name();
        const bool software = dev != nullptr && std::strstr(dev, "llvmpipe") != nullptr;
        if (!software) {
            gpuid = 0;
        }
        std::printf("ps5mm-interp: ncnn gpu[0] = %s -> gpuid %d\\n", dev != nullptr ? dev : "(null)", gpuid);
    } else {
        std::printf("ps5mm-interp: ncnn sees no Vulkan device -> gpuid -1 (CPU)\\n");
    }
    std::fflush(nullptr);
    auto * r = new RIFE(gpuid, false, false, uhd, threads, v2, v4);""",
    "interp: GPU first",
)

edit(
    APP / "audio_server.cpp",
    """    st = audiocpp_session_create(g_a.model, task, "offline", nullptr, nullptr, &g_a.session);
    if (st != AUDIOCPP_OK || g_a.session == nullptr) {
        err = last_error("could not create the session");
        release_engine();
        return false;
    }""",
    """    // backend_config = nullptr 在 audio.cpp 里就是「用 CPU」。PS5 上跑 TTS
    // 必须显式要 Vulkan，否则一句话要好几分钟。没有 Vulkan 的构建（PC 验证）
    // 会创建失败，那时才退回默认。
    audiocpp_backend_config be{};
    be.backend = "vulkan";
    be.device  = 0;
    be.threads = 0;
    st = audiocpp_session_create(g_a.model, task, "offline", &be, nullptr, &g_a.session);
    if (st != AUDIOCPP_OK || g_a.session == nullptr) {
        std::printf("ps5mm-audio: vulkan session failed (%s), falling back to the default backend\\n",
                    audiocpp_last_error() != nullptr ? audiocpp_last_error() : "?");
        std::fflush(nullptr);
        be.backend = nullptr;
        st = audiocpp_session_create(g_a.model, task, "offline", &be, nullptr, &g_a.session);
    }
    if (st != AUDIOCPP_OK || g_a.session == nullptr) {
        err = last_error("could not create the session");
        release_engine();
        return false;
    }""",
    "audio: Vulkan first",
)

# interp needs <cstring> for strstr and ncnn's gpu.h
edit(
    APP / "interp_server.cpp",
    """#include "rife.h\"""",
    """#include "rife.h"

#include "gpu.h"      // ncnn::get_gpu_count / get_gpu_info
#include <cstring>    // std::strstr""",
    "interp: includes",
)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--check":
        for path, old, new, tag in EDITS:
            src = path.read_text(encoding="utf-8")
            print(f"{'applied' if new in src else ('todo' if old in src else 'MISSING'):8s} {path.name}: {tag}")
        return 0
    if mode == "--revert":
        for path, old, new, tag in reversed(EDITS):
            src = path.read_text(encoding="utf-8")
            if new in src:
                path.write_text(src.replace(new, old, 1), encoding="utf-8")
        print("reverted")
        return 0
    failed = False
    for path, old, new, tag in EDITS:
        src = path.read_text(encoding="utf-8")
        if new in src:
            print(f"skip     {tag}")
            continue
        if src.count(old) != 1:
            print(f"FAILED   {tag}: anchor x{src.count(old)}", file=sys.stderr)
            failed = True
            continue
        path.write_text(src.replace(old, new, 1), encoding="utf-8")
        print(f"patched  {tag}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
