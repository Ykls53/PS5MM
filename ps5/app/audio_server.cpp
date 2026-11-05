// SPDX-License-Identifier: GPL-3.0-or-later
// PS5MM's audio engine: audio.cpp's C ABI on its own ggml and Vulkan backend,
// in the same process as the text, speech and picture engines.
//
// Routes:
//   POST /v1/audio/speech          OpenAI TTS -> audio/wav (RIFF)
//   GET  /health
//
// The ffmpeg-free path: audio.cpp already hands back interleaved float PCM with
// its own sample rate and channel count, so the RIFF header is written here.
//
// Symbol note: audio.cpp's internals are ACX_-prefixed (scripts/prefix-audio.sh);
// only the audiocpp_* C API keeps its upstream names.

#include "audio_server.hpp"

#include "audiocpp_c.h"

#include "cpp-httplib/httplib.h"
#include "nlohmann/json.hpp"

#include <sys/stat.h>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace {

using json = nlohmann::json;

struct Engine {
    audiocpp_registry * registry = nullptr;
    audiocpp_model *    model    = nullptr;
    audiocpp_session *  session  = nullptr;
    bool                ready    = false;
    std::string         model_path;
    std::string         task;
    std::string         out_dir;
    std::string         voice_ref;    // 参考音频（克隆家族用）
    std::string         voice_text;   // 参考音频的文字稿
    std::string         family;
    std::string         load_error;
    std::mutex          mu;
    std::atomic<long>   jobs{ 0 };
    std::atomic<long>   last_ms{ 0 };
    std::atomic<bool>   listening{ false };
};

Engine          g_a;
httplib::Server * g_svr = nullptr;

// 只认 PCM16 的 wav（qwen3 出的参考就是这种）。失败就返回 false，
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

const char * status_text(audiocpp_status s) {
    switch (s) {
        case AUDIOCPP_OK:                  return "ok";
        case AUDIOCPP_ERR_INVALID_ARGUMENT:return "invalid argument";
        case AUDIOCPP_ERR_UNSUPPORTED_FAMILY: return "unsupported family";
        case AUDIOCPP_ERR_LOAD_FAILED:     return "load failed";
        case AUDIOCPP_ERR_RUNTIME:         return "runtime error";
        case AUDIOCPP_ERR_OUT_OF_MEMORY:   return "out of memory";
        case AUDIOCPP_ERR_OUT_OF_RANGE:    return "out of range";
        case AUDIOCPP_ERR_NOT_AVAILABLE:   return "not available";
    }
    return "unknown";
}

// The last error is per-thread; fold it into one string for the caller.
std::string last_error(const char * what) {
    std::string out = what;
    if (const char * detail = audiocpp_last_error()) {
        if (detail[0] != '\0') {
            out += ": ";
            out += detail;
        }
    }
    return out;
}

void release_engine(void) {
    if (g_a.session) {
        audiocpp_session_free(g_a.session);
        g_a.session = nullptr;
    }
    if (g_a.model) {
        audiocpp_model_free(g_a.model);
        g_a.model = nullptr;
    }
    if (g_a.registry) {
        audiocpp_registry_free(g_a.registry);
        g_a.registry = nullptr;
    }
    g_a.ready = false;
    g_a.family.clear();
}

// Load registry -> model -> session. Caller holds g_a.mu.
bool load_locked(std::string & err) {
    if (g_a.ready) {
        return true;
    }
    release_engine();
    if (g_a.model_path.empty()) {
        err = "no model configured (put a .gguf in /data/PS5MM/audio/)";
        return false;
    }

    audiocpp_status st = audiocpp_registry_create(nullptr, &g_a.registry);
    if (st != AUDIOCPP_OK || g_a.registry == nullptr) {
        err = last_error("could not create the registry");
        return false;
    }

    std::printf("ps5mm-audio: loading %s (task %s)\n", g_a.model_path.c_str(),
                g_a.task.empty() ? "tts" : g_a.task.c_str());
    std::fflush(nullptr);

    // config/options NULL: the family is identified from the path, as --family
    // would be left out on the command line.
    st = audiocpp_model_load(g_a.registry, g_a.model_path.c_str(), nullptr, nullptr, &g_a.model);
    if (st != AUDIOCPP_OK || g_a.model == nullptr) {
        err = last_error("could not load the model");
        release_engine();
        return false;
    }
    if (const char * fam = audiocpp_model_family(g_a.model)) {
        g_a.family = fam;
    }

    const char * task = g_a.task.empty() ? "tts" : g_a.task.c_str();
    // 默认走 CPU。实测（2026-11-05）：backend = "vulkan" 时第一次合成就再也不返回
    // （RADV 上的 session/backend 初始化卡住），而同一份模型在 CPU 上 rtf ≈ 1.1，
    // 一句话几秒钟。想试 GPU 就把 PS5MM_AUDIO_BACKEND=vulkan 设上。
    const char * want_backend = std::getenv("PS5MM_AUDIO_BACKEND");
    audiocpp_backend_config be{};
    be.backend = (want_backend != nullptr && want_backend[0] != 0) ? want_backend : "cpu";
    be.device  = 0;
    be.threads = 0;
    st = audiocpp_session_create(g_a.model, task, "offline", &be, nullptr, &g_a.session);
    if (st != AUDIOCPP_OK || g_a.session == nullptr) {
        std::printf("ps5mm-audio: vulkan session failed (%s), falling back to the default backend\n",
                    audiocpp_last_error() != nullptr ? audiocpp_last_error() : "?");
        std::fflush(nullptr);
        be.backend = nullptr;
        st = audiocpp_session_create(g_a.model, task, "offline", &be, nullptr, &g_a.session);
    }
    if (st != AUDIOCPP_OK || g_a.session == nullptr) {
        err = last_error("could not create the session");
        release_engine();
        return false;
    }

    g_a.ready = true;
    std::printf("ps5mm-audio: ready, family %s, task %s\n",
                g_a.family.empty() ? "?" : g_a.family.c_str(), task);
    std::fflush(nullptr);
    return true;
}

// Interleaved float PCM -> 16-bit RIFF. Everything audio.cpp hands back is
// float; a WAV keeps the route playable by any client without a decoder.
std::string wav_from_pcm(const float * samples, size_t frames, int rate, int channels) {
    std::string out;
    if (samples == nullptr || frames == 0 || rate <= 0 || channels <= 0) {
        return out;
    }
    const uint32_t data_bytes = (uint32_t) (frames * (size_t) channels * 2u);
    const auto put32 = [&out](uint32_t v) {
        out.push_back((char) (v & 0xff));
        out.push_back((char) ((v >> 8) & 0xff));
        out.push_back((char) ((v >> 16) & 0xff));
        out.push_back((char) ((v >> 24) & 0xff));
    };
    const auto put16 = [&out](uint16_t v) {
        out.push_back((char) (v & 0xff));
        out.push_back((char) ((v >> 8) & 0xff));
    };
    out.reserve(44 + data_bytes);
    out.append("RIFF", 4);
    put32(36u + data_bytes);
    out.append("WAVE", 4);
    out.append("fmt ", 4);
    put32(16);                                        // PCM header size
    put16(1);                                         // PCM
    put16((uint16_t) channels);
    put32((uint32_t) rate);
    put32((uint32_t) (rate * channels * 2));          // byte rate
    put16((uint16_t) (channels * 2));                 // block align
    put16(16);                                        // bits per sample
    out.append("data", 4);
    put32(data_bytes);
    const size_t n = frames * (size_t) channels;
    for (size_t i = 0; i < n; ++i) {
        float v = samples[i];
        if (v > 1.0f) v = 1.0f;
        if (v < -1.0f) v = -1.0f;
        put16((uint16_t) (int16_t) std::lround(v * 32767.0f));
    }
    return out;
}

bool write_file(const std::string & path, const void * data, size_t n) {
    std::FILE * f = std::fopen(path.c_str(), "wb");
    if (f == nullptr) {
        return false;
    }
    const size_t wrote = std::fwrite(data, 1, n, f);
    std::fclose(f);
    return wrote == n;
}

void send_error(httplib::Response & res, int code, const std::string & msg) {
    res.status = code;
    res.set_content(json{ { "error", msg } }.dump(), "application/json");
}

json parse_body(const httplib::Request & req, httplib::Response & res) {
    try {
        return json::parse(req.body);
    } catch (const std::exception & e) {
        send_error(res, 400, std::string("bad JSON: ") + e.what());
        return json();
    }
}

void on_health(const httplib::Request &, httplib::Response & res) {
    json out{ { "ok", true },
              { "engine", "audio" },
              { "model_loaded", g_a.ready },
              { "family", g_a.family },
              { "task", g_a.task.empty() ? "tts" : g_a.task },
              { "jobs", (long) g_a.jobs.load() },
              { "last_ms", (long) g_a.last_ms.load() } };
    if (!g_a.ready && !g_a.load_error.empty()) {
        out["load_error"] = g_a.load_error;
    }
    res.set_content(out.dump(), "application/json");
}

// POST /v1/audio/speech  { input, voice?, language?, response_format? }
void on_speech(const httplib::Request & req, httplib::Response & res) {
    const json body = parse_body(req, res);
    if (body.is_null()) {
        return;
    }
    const std::string input = body.value("input", std::string());
    if (input.empty()) {
        send_error(res, 400, "input is empty");
        return;
    }
    const std::string language = body.value("language", std::string("zh"));
    // voice 可以是参考 wav 的路径（克隆家族要的就是这个）；留空就用设置里那份。
    const std::string voice = body.value("voice", g_a.voice_ref);
    const std::string ref_text = body.value("reference_text", g_a.voice_text);

    std::lock_guard<std::mutex> lock(g_a.mu);
    g_a.jobs++;
    std::string err;
    if (!load_locked(err)) {
        g_a.load_error = err;
        send_error(res, 503, err);
        return;
    }

    const int64_t t0 = (int64_t) (std::clock() * 1000 / CLOCKS_PER_SEC);

    audiocpp_request * request = audiocpp_request_create();
    if (request == nullptr) {
        send_error(res, 500, last_error("could not create the request"));
        return;
    }
    audiocpp_status st = audiocpp_request_set_text(request, input.c_str(), language.c_str());
    if (st != AUDIOCPP_OK) {
        err = last_error("set_text");
        audiocpp_request_free(request);
        send_error(res, 400, err);
        return;
    }
    if (!voice.empty()) {
        // 先按「参考音频」处理：qwen3_tts Base 这类克隆家族只认这个。
        std::vector<float> pcm;
        int                rate = 0, channels = 1;
        if (read_wav_pcm16(voice, pcm, rate, channels)) {
            (void) audiocpp_request_set_voice_audio(request, pcm.data(), pcm.size() / (size_t) channels, rate,
                                                    channels);
            if (!ref_text.empty()) {
                (void) audiocpp_request_set_option(request, "reference_text", ref_text.c_str());
            }
            std::printf("ps5mm-audio: voice reference %s (%d Hz, %d ch, %zu frames)\n", voice.c_str(), rate,
                        channels, pcm.size() / (size_t) channels);
            std::fflush(nullptr);
        } else {
            // 读不出来就当成内置音色名（老行为）。
            (void) audiocpp_request_set_voice_id(request, voice.c_str());
        }
    }

    audiocpp_result * result = nullptr;
    st = audiocpp_session_run(g_a.session, request, &result);
    audiocpp_request_free(request);
    if (st != AUDIOCPP_OK || result == nullptr) {
        err = last_error("run");
        if (result) {
            audiocpp_result_free(result);
        }
        send_error(res, 500, err);
        return;
    }

    const float * pcm = nullptr;
    size_t        frames = 0;
    int           rate = 0;
    int           channels = 0;
    st = audiocpp_result_audio(result, &pcm, &frames, &rate, &channels);
    if (st != AUDIOCPP_OK || pcm == nullptr || frames == 0) {
        // No audio: hand back whatever text the family produced, if any.
        const char * text = nullptr;
        const char * lang = nullptr;
        if (audiocpp_result_text(result, &text, &lang) == AUDIOCPP_OK && text != nullptr) {
            const std::string copied = text;
            audiocpp_result_free(result);
            res.set_content(json{ { "text", copied } }.dump(), "application/json");
            return;
        }
        audiocpp_result_free(result);
        send_error(res, 500, "the task produced no audio");
        return;
    }

    const std::string wav = wav_from_pcm(pcm, frames, rate, channels);
    audiocpp_result_free(result);
    if (wav.empty()) {
        send_error(res, 500, "could not encode the audio");
        return;
    }

    if (!g_a.out_dir.empty()) {
        char name[256];
        std::snprintf(name, sizeof name, "%s/audio-%ld.wav", g_a.out_dir.c_str(), g_a.jobs.load());
        write_file(name, wav.data(), wav.size());
    }

    const int64_t t1 = (int64_t) (std::clock() * 1000 / CLOCKS_PER_SEC);
    g_a.last_ms = (long) (t1 - t0);
    std::printf("ps5mm-audio: %zu frames %d Hz %d ch in %ld ms\n", frames, rate, channels,
                (long) g_a.last_ms.load());
    std::fflush(nullptr);
    res.set_content(wav, "audio/wav");
}

void on_options(const httplib::Request &, httplib::Response & res) {
    json out{ { "engine", "audio" }, { "model", g_a.model_path }, { "model_loaded", g_a.ready } };
    res.set_content(out.dump(), "application/json");
}

}  // namespace

int audio_server_start(const AudioModels & models, int port) {
    if (models.model != nullptr) {
        g_a.model_path = models.model;
    }
    if (models.voice_ref != nullptr) {
        g_a.voice_ref = models.voice_ref;
    }
    if (models.voice_text != nullptr) {
        g_a.voice_text = models.voice_text;
    }
    if (models.task != nullptr) {
        g_a.task = models.task;
    }
    if (models.output_dir != nullptr) {
        g_a.out_dir = models.output_dir;
    }

    auto * svr = new httplib::Server();
    svr->Get("/health", on_health);
    svr->Get("/v1/audio/options", on_options);
    svr->Post("/v1/audio/speech", on_speech);
    g_svr = svr;

    std::thread([port]() {
        g_a.listening = true;
        std::printf("ps5mm-audio: listening on :%d\n", port);
        std::fflush(nullptr);
        if (!g_svr->listen("0.0.0.0", port)) {
            std::printf("ps5mm-audio: could not listen on :%d\n", port);
            std::fflush(nullptr);
            g_a.listening = false;
        }
    }).detach();

    return 0;
}

void audio_server_terminate(void) {
    if (g_svr != nullptr) {
        g_svr->stop();
    }
    std::lock_guard<std::mutex> lock(g_a.mu);
    release_engine();
}

int audio_server_preload(void) {
    std::lock_guard<std::mutex> lock(g_a.mu);
    std::string err;
    if (!load_locked(err)) {
        g_a.load_error = err;
        std::printf("ps5mm-audio: preload failed: %s\n", err.c_str());
        std::fflush(nullptr);
        return -1;
    }
    return 0;
}

bool audio_server_ready(void) { return g_a.ready; }
bool audio_server_listening(void) { return g_a.listening.load(); }

std::string audio_server_family(void) { return g_a.family; }

long audio_server_last_ms(void) { return g_a.last_ms.load(); }
