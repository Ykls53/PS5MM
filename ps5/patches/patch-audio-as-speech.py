#!/usr/bin/env python3
"""Speech becomes audio.cpp, and nothing loads at startup.

Why: llama.cpp's mtmd audio path wedged the whole process on RADV twice (see
README). audio.cpp is the engine that exists for speech, runs qwen3_tts at
rtf≈1.1 even on the CPU, and manages its own backend. So:

  * the speech slot (8003) now starts audio_server with task "tts"
  * the separate "audio engine" slot goes away -- it would be the same engine
  * the reference voice comes from settings (audio_voice_ref / audio_voice_text)
  * nothing is loaded at startup: audio_server only loads on the first request,
    which is also what "don't pull models on boot" asks for

    python3 patch-audio-as-speech.py [--check|--revert]
"""
import sys
from pathlib import Path

APP = Path("/home/yk/PS5MM/ps5/app")
EDITS = []


def edit(path, old, new, tag):
    EDITS.append((path, old, new, tag))


# ------------------------------------------------------------------ settings
edit(
    APP / "settings.hpp",
    """    std::string audio_model = "/data/PS5MM/audio/model.gguf";
    std::string audio_dir   = "/data/PS5MM/audio";   // 渲染出来的 .wav 落这里""",
    """    std::string audio_model = "/data/PS5MM/audio/model.gguf";
    std::string audio_dir   = "/data/PS5MM/audio";   // 渲染出来的 .wav 落这里
    // 语音现在就是 audio.cpp 的 qwen3_tts：克隆家族要一段参考音频 + 文字稿，
    // 否则第一次请求会被拒。留空则退化成「内置音色名」那条老路。
    std::string audio_voice_ref;
    std::string audio_voice_text;""",
    "settings.hpp: fields",
)

edit(
    APP / "settings.cpp",
    """    s.audio_model   = j.value("audio_model", s.audio_model);""",
    """    s.audio_model   = j.value("audio_model", s.audio_model);
    s.audio_voice_ref  = j.value("audio_voice_ref", s.audio_voice_ref);
    s.audio_voice_text = j.value("audio_voice_text", s.audio_voice_text);""",
    "settings.cpp: load",
)

edit(
    APP / "settings.cpp",
    """        { "audio_model", s.audio_model },   { "audio_dir", s.audio_dir },""",
    """        { "audio_model", s.audio_model },   { "audio_dir", s.audio_dir },
        { "audio_voice_ref", s.audio_voice_ref }, { "audio_voice_text", s.audio_voice_text },""",
    "settings.cpp: save",
)

# ------------------------------------------------------------------ main.cpp: speech slot
edit(
    APP / "main.cpp",
    """        std::thread([tts_model, tts_codec, voices_dir, tts_slot] {
            if (tts_model.empty() || access(tts_model.c_str(), F_OK) != 0 || tts_codec.empty() ||
                access(tts_codec.c_str(), F_OK) != 0) {
                std::printf("ps5mm-app: no speech model (see Settings)\\n");
                std::fflush(nullptr);
                if (!tts_model.empty()) {
                    tts_server_abandon();  // 指了路径但文件不在：槽位卡显示「出错」，不是永远「加载中」
                }
                return;
            }
            const int p = ps5mm::port_of_slot(tts_slot);
            std::printf("ps5mm-app: speech engine starting on :%d (%s)\\n", p, tts_model.c_str());
            std::fflush(nullptr);
            if (tts_server_start(tts_model.c_str(), tts_codec.c_str(), voices_dir.c_str(), p) == 0) {
                notify(("PS5MM: speech ready on :" + std::to_string(p)).c_str());
            } else {
                notify("PS5MM: the speech model did not load; text still works");
            }
        }).detach();""",
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
    "main.cpp: speech slot uses audio.cpp",
)

# ------------------------------------------------------------------ main.cpp: drop the duplicate audio slot
edit(
    APP / "main.cpp",
    """        // 音频引擎：audio.cpp 的 C API（ACX_ 前缀），占第一个空闲槽位。
        // 模型约定在 /data/PS5MM/audio/model.gguf；没有就只起路由，等第一次请求。
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
                std::thread([audio_port, a_model = boot.audio_model, a_dir = boot.audio_dir] {
                    // 路径来自 settings；按值捕获 std::string，c_str() 在 lambda 里一直有效
                    AudioModels audio_models{ a_model.c_str(), "tts", a_dir.c_str() };
                    std::printf("ps5mm-app: audio engine starting on :%d (loads on first request)\\n", audio_port);
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
    """        // 音频引擎已经并进语音槽了：同一个 audio.cpp，不值得起两份。
""",
    "main.cpp: drop duplicate audio slot",
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
