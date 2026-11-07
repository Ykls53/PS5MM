#!/usr/bin/env python3
# Wire the VoxCPM speech engine into PS5MM's main.cpp.
#   --check   report whether the patch is present
#   --revert  restore main.cpp.bak-voxcpm
import pathlib, sys, shutil

p = pathlib.Path("/home/yk/PS5MM/ps5/app/main.cpp")
bak = p.with_name("main.cpp.bak-voxcpm")

if "--revert" in sys.argv:
    if bak.exists():
        shutil.copyfile(bak, p)
        print("reverted")
    else:
        print("no backup")
    sys.exit(0)

src = p.read_text(encoding="utf-8")

patches = []

patches.append((
    '#include "tts_server.hpp"\n',
    '#include "tts_server.hpp"\n#include "voxcpm_server.hpp"\n',
))

patches.append((
    'std::atomic<int> g_server_rc{ -1 };   // llama-server\'s exit code once it returns; -1 while it runs\n',
    'std::atomic<int> g_server_rc{ -1 };   // llama-server\'s exit code once it returns; -1 while it runs\n'
    'std::atomic<bool> g_speech_voxcpm{ false };   // speech slot is served by VoxCPM, not llama.cpp\n',
))

old_start = '''        // 语音引擎 = llama.cpp（tts_server），保守版。
        // 这条路在 PS5 上有过出音频的记录；但 tts_server 里已经把主模型和投影器
        // 都钉在 CPU 上（GPU 上实测会锁死整个进程），所以是「能用但慢」。
        std::thread([tts_model, tts_codec, voices_dir, tts_slot] {
            if (tts_model.empty() || access(tts_model.c_str(), F_OK) != 0 || tts_codec.empty() ||
                access(tts_codec.c_str(), F_OK) != 0) {
                std::printf("ps5mm-app: no speech model (see Settings)\\n");
                std::fflush(nullptr);
                if (!tts_model.empty()) {
                    tts_server_abandon();
                }
                return;
            }
            const int speech_port = ps5mm::port_of_slot(tts_slot);
            std::printf("ps5mm-app: speech engine (llama.cpp, CPU) on :%d (%s)\\n", speech_port, tts_model.c_str());
            std::fflush(nullptr);
            if (tts_server_start(tts_model.c_str(), tts_codec.c_str(), voices_dir.c_str(), speech_port) == 0) {
                notify(("PS5MM: speech ready on :" + std::to_string(speech_port)).c_str());
            } else {
                notify("PS5MM: the speech model did not load; text still works");
            }
        }).detach();'''

new_start = '''        // 语音引擎二选一：
        //   tts_backbone 指向 VoxCPM 的单文件 GGUF（名字里带 voxcpm）→ VoxCPM.cpp（Vulkan）
        //   否则走原来的 llama.cpp Qwen3-TTS（CPU，需要 mmproj）
        // VoxCPM 无状态、单文件、跑 Vulkan；老引擎连发会退化，且 GPU 上会锁死进程。
        const bool use_voxcpm = tts_model.find("voxcpm") != std::string::npos;
        g_speech_voxcpm = use_voxcpm;
        std::thread([tts_model, tts_codec, voices_dir, tts_slot, use_voxcpm] {
            if (tts_model.empty() || access(tts_model.c_str(), F_OK) != 0) {
                std::printf("ps5mm-app: no speech model (see Settings)\\n");
                std::fflush(nullptr);
                if (!tts_model.empty() && !use_voxcpm) {
                    tts_server_abandon();
                }
                return;
            }
            const int speech_port = ps5mm::port_of_slot(tts_slot);
            if (use_voxcpm) {
                std::printf("ps5mm-app: speech engine (VoxCPM, Vulkan) on :%d (%s)\\n", speech_port,
                            tts_model.c_str());
                std::fflush(nullptr);
                if (voxcpm_server_start(tts_model.c_str(), voices_dir.c_str(), speech_port) == 0) {
                    notify(("PS5MM: speech ready on :" + std::to_string(speech_port)).c_str());
                } else {
                    notify("PS5MM: the speech model did not load; text still works");
                }
                return;
            }
            if (tts_codec.empty() || access(tts_codec.c_str(), F_OK) != 0) {
                std::printf("ps5mm-app: no speech codec (see Settings)\\n");
                std::fflush(nullptr);
                tts_server_abandon();
                return;
            }
            std::printf("ps5mm-app: speech engine (llama.cpp, CPU) on :%d (%s)\\n", speech_port,
                        tts_model.c_str());
            std::fflush(nullptr);
            if (tts_server_start(tts_model.c_str(), tts_codec.c_str(), voices_dir.c_str(), speech_port) == 0) {
                notify(("PS5MM: speech ready on :" + std::to_string(speech_port)).c_str());
            } else {
                notify("PS5MM: the speech model did not load; text still works");
            }
        }).detach();'''

patches.append((old_start, new_start))

patches.append((
    '            const int tts = tts_server_status();\n',
    '            const int tts = g_speech_voxcpm ? voxcpm_server_status() : tts_server_status();\n',
))
patches.append((
    '                        : tts == 2                ? (tts_server_busy() ? "生成中" : "就绪")\n',
    '                        : tts == 2                ? ((g_speech_voxcpm ? voxcpm_server_busy() : tts_server_busy()) ? "生成中" : "就绪")\n',
))
patches.append((
    '            c.requests  = (uint64_t) tts_server_requests();\n',
    '            c.requests  = (uint64_t) (g_speech_voxcpm ? voxcpm_server_requests() : tts_server_requests());\n',
))

patches.append((
    '    tts_server_terminate();\n    sd_server_terminate();\n',
    '    tts_server_terminate();\n    voxcpm_server_terminate();\n    sd_server_terminate();\n',
    2,
))

if "--check" in sys.argv:
    for entry in patches:
        old, new = entry[0], entry[1]
        print(("OK  " if new in src else "MISS"), new.splitlines()[0][:70])
    sys.exit(0)

for entry in patches:
    old, new = entry[0], entry[1]
    expect = entry[2] if len(entry) > 2 else 1
    n = src.count(old)
    if n != expect:
        raise SystemExit(f"patch anchor matched {n} times (expected {expect}): {old.splitlines()[0][:60]}")
    src = src.replace(old, new)

if not bak.exists():
    shutil.copyfile(p, bak)
p.write_text(src, encoding="utf-8")
print("patched main.cpp")
