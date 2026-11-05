#!/usr/bin/env python3
"""Make audio.cpp the speech engine: give it a reference voice.

Qwen3-TTS Base is a clone-family model: it needs a reference clip plus that
clip's transcript before it will speak. audio_server only ever called
`audiocpp_request_set_voice_id` (a built-in voice name), so a Base model always
answered "requires voice clone reference audio".

This adds:
  * a tiny PCM16 WAV reader (the format our own TTS writes)
  * AudioModels.voice_ref / voice_text, filled from settings
  * on_speech: a `voice` that is a readable wav goes through set_voice_audio +
    reference_text; otherwise it falls back to the old voice_id path.

    python3 patch-audio-voice-ref.py [--check|--revert]
"""
import sys
from pathlib import Path

APP = Path("/home/yk/PS5MM/ps5/app")
EDITS = []


def edit(path, old, new, tag):
    EDITS.append((path, old, new, tag))


# ------------------------------------------------------------------ header
edit(
    APP / "audio_server.hpp",
    """struct AudioModels {
    const char * model;       // a .gguf, or the model's directory
    const char * task;        // tts / gen / clone / vc / ... (audiocpp's tokens)
    const char * output_dir;  // where rendered .wav files land
};""",
    """struct AudioModels {
    const char * model;       // a .gguf, or the model's directory
    const char * task;        // tts / gen / clone / vc / ... (audiocpp's tokens)
    const char * output_dir;  // where rendered .wav files land
    // 克隆类模型（qwen3_tts Base 这类）要一段参考音频和它的文字稿，
    // 否则第一次请求就报 "requires voice clone reference audio"。
    const char * voice_ref;   // 参考 wav 的绝对路径，可空
    const char * voice_text;  // 上面那段 wav 说的是什么
};""",
    "hpp: AudioModels fields",
)

# ------------------------------------------------------------------ wav reader
edit(
    APP / "audio_server.cpp",
    """const char * status_text(audiocpp_status s) {""",
    """// 只认 PCM16 的 wav（qwen3 出的参考就是这种）。失败就返回 false，
// 调用方退回 voice_id 那条老路。
bool read_wav_pcm16(const std::string & path, std::vector<float> & out, int & rate, int & channels) {
    FILE * f = std::fopen(path.c_str(), "rb");
    if (f == nullptr) {
        return false;
    }
    char riff[12];
    if (std::fread(riff, 1, 12, f) != 12 || std::memcmp(riff, "RIFF", 4) != 0 ||
        std::memcmp(riff + 8, "WAVE", 4) != 0) {
        std::fclose(f);
        return false;
    }
    int              format = 0, bits = 0;
    std::vector<char> data;
    rate     = 0;
    channels = 0;
    for (;;) {
        char hdr[8];
        if (std::fread(hdr, 1, 8, f) != 8) {
            break;
        }
        const uint32_t len = (uint32_t) (unsigned char) hdr[4] | ((uint32_t) (unsigned char) hdr[5] << 8) |
                             ((uint32_t) (unsigned char) hdr[6] << 16) | ((uint32_t) (unsigned char) hdr[7] << 24);
        if (std::memcmp(hdr, "fmt ", 4) == 0) {
            std::vector<char> fmt(len);
            if (std::fread(fmt.data(), 1, len, f) != len) {
                break;
            }
            if (len >= 16) {
                format   = (unsigned char) fmt[0] | ((unsigned char) fmt[1] << 8);
                channels = (unsigned char) fmt[2] | ((unsigned char) fmt[3] << 8);
                rate     = (int) ((unsigned char) fmt[4] | ((unsigned char) fmt[5] << 8) |
                              ((unsigned char) fmt[6] << 16) | ((unsigned char) fmt[7] << 24));
                bits     = (unsigned char) fmt[14] | ((unsigned char) fmt[15] << 8);
            }
        } else if (std::memcmp(hdr, "data", 4) == 0) {
            data.resize(len);
            if (std::fread(data.data(), 1, len, f) != len) {
                data.clear();
            }
            break;
        } else {
            std::fseek(f, (long) len + (long) (len & 1), SEEK_CUR);
        }
    }
    std::fclose(f);
    if (format != 1 || bits != 16 || channels <= 0 || rate <= 0 || data.size() < 2) {
        return false;
    }
    const size_t n = data.size() / 2;
    out.resize(n);
    for (size_t i = 0; i < n; ++i) {
        const int16_t v = (int16_t) ((unsigned char) data[i * 2] | ((unsigned char) data[i * 2 + 1] << 8));
        out[i]           = (float) v / 32768.0f;
    }
    return true;
}

const char * status_text(audiocpp_status s) {""",
    "cpp: wav reader",
)

# ------------------------------------------------------------------ engine fields
edit(
    APP / "audio_server.cpp",
    """    std::string         out_dir;
    std::string         family;""",
    """    std::string         out_dir;
    std::string         voice_ref;    // 参考音频（克隆家族用）
    std::string         voice_text;   // 参考音频的文字稿
    std::string         family;""",
    "cpp: engine fields",
)

# ------------------------------------------------------------------ on_speech
edit(
    APP / "audio_server.cpp",
    """    const std::string language = body.value("language", std::string("zh"));
    // A named voice is a reference clip path when the family clones, otherwise
    // ignored: audiocpp takes the reference as audio, not as a name.
    const std::string voice = body.value("voice", std::string());""",
    """    const std::string language = body.value("language", std::string("zh"));
    // voice 可以是参考 wav 的路径（克隆家族要的就是这个）；留空就用设置里那份。
    const std::string voice = body.value("voice", g_a.voice_ref);
    const std::string ref_text = body.value("reference_text", g_a.voice_text);""",
    "cpp: on_speech head",
)

edit(
    APP / "audio_server.cpp",
    """    if (!voice.empty()) {
        // Only meaningful for cloning families; failures are not fatal here.
        (void) audiocpp_request_set_voice_id(request, voice.c_str());
    }""",
    """    if (!voice.empty()) {
        // 先按「参考音频」处理：qwen3_tts Base 这类克隆家族只认这个。
        std::vector<float> pcm;
        int                rate = 0, channels = 1;
        if (read_wav_pcm16(voice, pcm, rate, channels)) {
            (void) audiocpp_request_set_voice_audio(request, pcm.data(), pcm.size() / (size_t) channels, rate,
                                                    channels);
            if (!ref_text.empty()) {
                (void) audiocpp_request_set_option(request, "reference_text", ref_text.c_str());
            }
            std::printf("ps5mm-audio: voice reference %s (%d Hz, %d ch, %zu frames)\\n", voice.c_str(), rate,
                        channels, pcm.size() / (size_t) channels);
            std::fflush(nullptr);
        } else {
            // 读不出来就当成内置音色名（老行为）。
            (void) audiocpp_request_set_voice_id(request, voice.c_str());
        }
    }""",
    "cpp: on_speech voice",
)

# ------------------------------------------------------------------ take models
edit(
    APP / "audio_server.cpp",
    """int audio_server_start(const AudioModels & models, int port) {
    if (models.model != nullptr) {
        g_a.model_path = models.model;
    }""",
    """int audio_server_start(const AudioModels & models, int port) {
    if (models.model != nullptr) {
        g_a.model_path = models.model;
    }
    if (models.voice_ref != nullptr) {
        g_a.voice_ref = models.voice_ref;
    }
    if (models.voice_text != nullptr) {
        g_a.voice_text = models.voice_text;
    }""",
    "cpp: start takes voice",
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
