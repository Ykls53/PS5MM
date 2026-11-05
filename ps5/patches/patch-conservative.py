#!/usr/bin/env python3
"""Conservative build: old behaviour, plus only the fixes that cannot hurt.

What goes back to the old way:
  * 插帧 gpuid 钉死 -1（CPU）。GPU 路径（ncnn Vulkan 初始化）在 PS5 上从来没验过，
    崩了会把整个 app 带走。CPU 上 256x256 一帧 0.2 秒（PC 32 核），PS5 估计 1-2 秒，够用。
  * 语音回到 llama.cpp（tts_server）——那条路在 PS5 上有过出音频的记录。
    但**保持 CPU**（n_gpu_layers=0 + mp.use_gpu=false），因为 GPU 上实测会锁死。
  * audio.cpp 引擎恢复独立的 8004 槽（旧行为），它自己是懒加载，不占资源。

What stays (the safe fixes):
  * 图片/视频两套模型互斥切换（换视频后图片不再废）
  * 设置页「视频编码器 / 视频 VAE」两行
  * n_gpu_layers 不再写死 999（没有 GPU 后端时自动 0，避免 ggml_abort）
  * RIFE CPU 路径空指针修复
  * enable_mmap = false（PS5 上 mmap 卡死）

    python3 patch-conservative.py [--check|--revert]
"""
import sys
from pathlib import Path

APP = Path("/home/yk/PS5MM/ps5/app")
EDITS = []


def edit(path, old, new, tag):
    EDITS.append((path, old, new, tag))


# ---------------------------------------------------------------- interp: back to CPU
edit(
    APP / "interp_server.cpp",
    """    int gpuid = -1;
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
    """    // 保守版：钉死 CPU。GPU 那条路要过 ncnn 的 Vulkan 初始化，这条路在 PS5 上
    // 从来没验过，一旦崩就把整个 app 带走（这个代价我们已经付过三次）。
    // CPU 上 256x256 一帧 0.2 秒（PC 32 核），PS5 估计 1~2 秒，够用。
    // 要试验 GPU：把下面这行改成 ncnn::get_gpu_count() > 0 ? 0 : -1。
    const int gpuid = -1;
    std::printf("ps5mm-interp: gpuid %d (CPU, conservative)\\n", gpuid);
    std::fflush(nullptr);
    auto * r = new RIFE(gpuid, false, false, uhd, threads, v2, v4);""",
    "interp: pin to CPU",
)

# ---------------------------------------------------------------- main: speech back to llama.cpp
edit(
    APP / "main.cpp",
    """        // 语音引擎 = audio.cpp（qwen3_tts）。llama.cpp 的 mtmd 音频路径在 RADV 上
        // 会把整个进程锁死（2026-11-05 实测两次，8002/8004/8005/8099 全超时），
        // 而 audio.cpp 本来就是干这个的，CPU 上 rtf 也有 1.1。
        std::thread([a_model = boot.audio_model, a_dir = boot.audio_dir,
                     a_vref = boot.audio_voice_ref, a_vtext = boot.audio_voice_text, tts_slot] {
            if (a_model.empty() || access(a_model.c_str(), F_OK) != 0) {
                std::printf("ps5mm-app: no speech model (see Settings)\\n");
                std::fflush(nullptr);
                tts_server_abandon();
                return;
            }
            const int speech_port = ps5mm::port_of_slot(tts_slot);
            AudioModels speech_models{ a_model.c_str(), "tts", a_dir.c_str(), a_vref.c_str(), a_vtext.c_str() };
            std::printf("ps5mm-app: speech engine (audio.cpp) on :%d (%s)\\n", speech_port, a_model.c_str());
            std::fflush(nullptr);
            if (audio_server_start(speech_models, speech_port) != 0) {
                notify("PS5MM: the speech engine did not start");
                return;
            }
            notify(("PS5MM: speech on :" + std::to_string(speech_port)).c_str());
        }).detach();""",
    """        // 语音引擎 = llama.cpp（tts_server），保守版。
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
        }).detach();""",
    "main: speech back to llama.cpp",
)

# ---------------------------------------------------------------- main: audio slot comes back
edit(
    APP / "main.cpp",
    """        // 音频引擎已经并进语音槽了：同一个 audio.cpp，不值得起两份。
""",
    """        // 音频引擎：audio.cpp 的 C API，占第一个空闲槽位。
        // 懒加载：只起路由，第一次请求才 load。模型路径来自 settings。
        {
            int audio_slot = 0;
            for (int s = 1; s <= 5; ++s) {
                if (s != boot.text_slot && s != boot.picture_slot && s != boot.speech_slot) {
                    audio_slot = s;
                    break;
                }
            }
            if (audio_slot != 0) {
                const int audio_port = ps5mm::port_of_slot(audio_slot);
                std::thread([audio_port, a_model = boot.audio_model, a_dir = boot.audio_dir,
                             a_vref = boot.audio_voice_ref, a_vtext = boot.audio_voice_text] {
                    AudioModels audio_models{ a_model.c_str(), "tts", a_dir.c_str(), a_vref.c_str(),
                                              a_vtext.c_str() };
                    std::printf("ps5mm-app: audio engine on :%d (loads on first request)\\n", audio_port);
                    std::fflush(nullptr);
                    if (audio_server_start(audio_models, audio_port) != 0) {
                        notify("PS5MM: the audio engine did not start");
                        return;
                    }
                    notify(("PS5MM: audio on :" + std::to_string(audio_port)).c_str());
                }).detach();
            }
        }
""",
    "main: audio slot restored",
)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--check":
        for path, old, new, tag in EDITS:
            src = path.read_text(encoding="utf-8")
            print(f"{'applied' if new in src else ('todo' if old in src else 'MISSING'):8s} {tag}")
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
