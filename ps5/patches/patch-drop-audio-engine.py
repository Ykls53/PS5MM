#!/usr/bin/env python3
"""删掉 audio.cpp 引擎（8004 让给视频）。

理由（有据）：
  * 5 次真机尝试，family 字段永远是空，model_load 一次没成功
  * 它的 gguf 是自家格式，和 llama/sd 的约定不兼容
  * 链接进来 197 MB（libengine_runtime 134 MB + libggml-vulkan 60 MB）
  * 每次试它都把整个 payload 链拖垮，只能物理关机

做法：
  1. main.cpp 删掉音频引擎那段（只影响 8004 的归属）
  2. build-app.sh 里 audio 的链接逻辑保留（目录不在了自然跳过）
  3. .deps/audio-acx 改名备份，随时能恢复

    python3 patch-drop-audio-engine.py [--check|--revert]
"""
import sys
from pathlib import Path

MAIN = Path("/home/yk/PS5MM/ps5/app/main.cpp")

OLD = """        // 音频引擎：audio.cpp 的 C API，占第一个空闲槽位。
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

        // 3D 引擎：TRELLIS.2 图生 3D（TRX_ 前缀），占 audio 之后的下一个空闲槽位。"""

NEW = """        // audio.cpp 引擎已移除（2026-11-05）：
        //   5 次真机尝试全部失败，它的 model_load 一进去就不返回，还会把整个
        //   payload 链拖死（只能物理关机）。它的 gguf 是自家格式，和 llama/sd
        //   的约定不兼容。8004 这个槽位改给视频用。
        //   代码和 .deps/audio-acx 都留着，需要时能随时接回来。

        // 3D 引擎：TRELLIS.2 图生 3D（TRX_ 前缀），占 video 之后的下一个空闲槽位。"""


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = MAIN.read_text(encoding="utf-8")
    if mode == "--check":
        print(f"old={src.count(OLD)} new={src.count(NEW)}")
        return 0
    if mode == "--revert":
        if NEW in src:
            MAIN.write_text(src.replace(NEW, OLD, 1), encoding="utf-8")
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
    MAIN.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched: audio engine removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
