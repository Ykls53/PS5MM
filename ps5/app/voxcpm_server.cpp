// SPDX-License-Identifier: GPL-3.0-or-later
// PS5MM's speech engine, second generation: VoxCPM.cpp behind OpenAI's
// /v1/audio/speech, in the same process as the text and image engines.
//
// One GGUF holds the talker and the AudioVAE. The engine is stateless per
// request (no KV cache carried between sentences), and runs on Vulkan — the
// only GPU path a PS5 native title has.
//
// The reference voice is a WAV/MP3/FLAC file in <voices_dir>/; its basename
// (without extension) is the request's "voice". The matching transcription is
// read from <basename>.txt when present, otherwise a built-in sentence is used.

#include "voxcpm_server.hpp"

#include "voxcpm/audio_io.h"
#include "voxcpm/server_common.h"

#include "cpp-httplib/httplib.h"
#include "nlohmann/json.hpp"

#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace {

using json = nlohmann::json;

constexpr int kDefaultThreads = 6;   // the title leaves two cores to the system
constexpr const char * kDefaultPrompt = "对，这就是我，万人敬仰的太乙真人。";

int64_t now_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count();
}

struct Engine {
    std::unique_ptr<voxcpm::VoxCPMServiceCore> core;
    std::unique_ptr<voxcpm::VoiceStore>        store;
    std::string       model_path;
    std::string       voices_dir;
    int               sample_rate = 24000;
    std::atomic<long> requests{ 0 };
    // 0 not configured, 1 loading, 2 ready, -1 failed — the slot card reads it.
    std::atomic<int>  status{ 0 };
    std::atomic<bool> busy{ false };
    std::mutex        mu;
};

Engine            g_e;
httplib::Server   g_svr;
std::thread       g_thread;
std::atomic<bool> g_stop{ false };

std::string read_file(const std::string & path) {
    std::string out;
    FILE * f = std::fopen(path.c_str(), "rb");
    if (f == nullptr) {
        return out;
    }
    char   buf[65536];
    size_t n = 0;
    while ((n = std::fread(buf, 1, sizeof buf, f)) > 0) {
        out.append(buf, n);
    }
    std::fclose(f);
    return out;
}

std::string trim(std::string s) {
    while (!s.empty() && (s.back() == '\n' || s.back() == '\r' || s.back() == ' ' || s.back() == '\t')) {
        s.pop_back();
    }
    size_t i = 0;
    while (i < s.size() && (s[i] == ' ' || s[i] == '\t')) {
        ++i;
    }
    return s.substr(i);
}

// A voice id from the request: file name or bare id, extension dropped.
std::string voice_id(const std::string & voice) {
    std::string name = voice;
    const size_t slash = name.find_last_of('/');
    if (slash != std::string::npos) {
        name = name.substr(slash + 1);
    }
    const size_t dot = name.find_last_of('.');
    if (dot != std::string::npos) {
        name = name.substr(0, dot);
    }
    return name;
}

// Find <voices_dir>/<id> with any supported extension.
std::string find_voice_file(const std::string & id) {
    static const char * kExts[] = { ".wav", ".mp3", ".flac" };
    for (const char * ext : kExts) {
        const std::string p = g_e.voices_dir + "/" + id + ext;
        if (access(p.c_str(), F_OK) == 0) {
            return p;
        }
    }
    return std::string();
}

// Register a voice on demand. Caller holds g_e.mu.
bool ensure_voice(const std::string & id, voxcpm::PromptFeatures & out, std::string & err) {
    if (id.empty()) {
        err = "voice is empty";
        return false;
    }
    if (g_e.store->has_voice(id)) {
        out = g_e.store->load_voice(id);
        return true;
    }
    const std::string file = find_voice_file(id);
    if (file.empty()) {
        err = "no such voice: " + id;
        return false;
    }
    const std::string raw = read_file(file);
    if (raw.empty()) {
        err = "could not read " + file;
        return false;
    }
    voxcpm::DecodedAudio decoded;
    try {
        decoded = voxcpm::decode_audio_from_memory(raw.data(), raw.size());
    } catch (const std::exception & e) {
        err = std::string("could not decode ") + file + ": " + e.what();
        return false;
    }
    if (decoded.samples.empty() || decoded.sample_rate <= 0) {
        err = "empty audio in " + file;
        return false;
    }
    std::string text = trim(read_file(g_e.voices_dir + "/" + id + ".txt"));
    if (text.empty()) {
        text = kDefaultPrompt;
    }
    const std::vector<float> mono = voxcpm::convert_to_mono(decoded);
    const int64_t t0 = now_ms();
    out = g_e.core->encode_prompt_audio(id, text, mono, decoded.sample_rate);
    g_e.store->save_voice(out);
    std::printf("ps5mm-voxcpm: voice %s registered from %s (%d frames) in %lld ms\n", id.c_str(),
                file.c_str(), out.prompt_audio_length,
                (long long) (now_ms() - t0));
    std::fflush(nullptr);
    return true;
}

// Synthesize one sentence into a WAV. Holds the engine lock (the core does too).
bool synthesize(const std::string & text, const std::string & voice, float speed, std::string & wav,
                std::string & err) {
    std::lock_guard<std::mutex> lock(g_e.mu);
    if (!g_e.core || !g_e.core->loaded()) {
        err = "the speech model is not loaded";
        return false;
    }
    g_e.busy = true;
    const auto done = [](void *) { g_e.busy = false; };
    std::unique_ptr<void, decltype(done)> busy_guard(reinterpret_cast<void *>(1), done);

    voxcpm::PromptFeatures prompt;
    if (!ensure_voice(voice_id(voice), prompt, err)) {
        return false;
    }

    voxcpm::SynthesisRequest request;
    request.text = text;
    request.prompt = std::move(prompt);
    request.cfg_value = 2.0f;
    request.inference_timesteps = 10;

    const int64_t t0 = now_ms();
    voxcpm::SynthesisResult result;
    try {
        result = g_e.core->synthesize(request);
    } catch (const std::exception & e) {
        err = std::string("synthesis failed: ") + e.what();
        return false;
    }
    if (result.waveform.empty()) {
        err = "no audio came out";
        return false;
    }
    if (speed > 0.0f && speed != 1.0f) {
        result.waveform = voxcpm::resample_audio_linear(result.waveform, (double) speed);
    }
    const std::vector<uint8_t> bytes = voxcpm::encode_audio(
        voxcpm::AudioResponseFormat::Wav, result.waveform, result.sample_rate);
    wav.assign(reinterpret_cast<const char *>(bytes.data()), bytes.size());
    std::printf("ps5mm-voxcpm: %d frames, %d Hz, %zu bytes of wav in %lld ms\n",
                result.generated_frames, result.sample_rate, bytes.size(),
                (long long) (now_ms() - t0));
    std::fflush(nullptr);
    return true;
}

void on_speech(const httplib::Request & req, httplib::Response & res) {
    json body = json::parse(req.body, nullptr, false);
    if (body.is_discarded() || !body.is_object()) {
        res.status = 400;
        res.set_content(R"({"error":"the body is not a JSON object"})", "application/json");
        return;
    }
    const std::string text = body.value("input", std::string());
    if (text.empty()) {
        res.status = 400;
        res.set_content(R"({"error":"input is empty"})", "application/json");
        return;
    }
    const std::string voice = body.value("voice", std::string("default.wav"));
    const float       speed = body.value("speed", 1.0f);

    g_e.requests++;
    std::string wav;
    std::string err;
    if (!synthesize(text, voice, speed, wav, err)) {
        std::printf("ps5mm-voxcpm: %s\n", err.c_str());
        std::fflush(nullptr);
        res.status = 500;
        res.set_content(json{ { "error", err } }.dump(), "application/json");
        return;
    }
    res.set_content(std::move(wav), "audio/wav");
}

// POST /unload — release the VoxCPM weights (about 1.5 GiB with the 0.5B q8_0).
void on_unload(const httplib::Request &, httplib::Response & res) {
    std::lock_guard<std::mutex> lock(g_e.mu);
    const bool had = (bool) g_e.core;
    g_e.core.reset();
    g_e.status = 0;
    std::printf("ps5mm-voxcpm: unloaded (had=%d)\n", (int) had);
    std::fflush(nullptr);
    res.set_content(json{ { "ok", true }, { "engine", "voxcpm" }, { "unloaded", had } }.dump(),
                    "application/json");
}

void on_health(const httplib::Request &, httplib::Response & res) {
    json out{ { "ok", g_e.core && g_e.core->loaded() },
              { "engine", "voxcpm" },
              { "requests", (long) g_e.requests.load() },
              { "sample_rate", g_e.sample_rate },
              { "model", g_e.model_path } };
    res.set_content(out.dump(), "application/json");
}

void on_voices(const httplib::Request &, httplib::Response & res) {
    json names = json::array();
    if (DIR * d = opendir(g_e.voices_dir.c_str())) {
        while (dirent * e = readdir(d)) {
            const std::string n = e->d_name;
            const bool audio = n.size() > 4 &&
                               (n.rfind(".wav") == n.size() - 4 || n.rfind(".mp3") == n.size() - 4 ||
                                n.rfind(".flac") == n.size() - 5);
            if (audio) {
                names.push_back(n);
            }
        }
        closedir(d);
    }
    res.set_content(json{ { "voices", names } }.dump(), "application/json");
}

}  // namespace

int voxcpm_server_start(const char * model_path, const char * voices_dir, int port) {
    if (model_path == nullptr || model_path[0] == 0) {
        return -1;
    }
    g_e.model_path = model_path;
    g_e.voices_dir = voices_dir != nullptr ? voices_dir : "";
    g_e.status     = 1;
    auto fail_guard = std::unique_ptr<void, void (*)(void *)>(reinterpret_cast<void *>(1), [](void *) {
        g_e.status = -1;
    });

    if (!g_e.voices_dir.empty()) {
        mkdir(g_e.voices_dir.c_str(), 0777);
    }

    std::printf("ps5mm-voxcpm: loading %s\n", model_path);
    std::fflush(nullptr);
    const int64_t t0 = now_ms();

    const unsigned hw = std::thread::hardware_concurrency();
    const int threads = hw > 2 ? (int) hw - 2 : kDefaultThreads;

    try {
        g_e.core = std::make_unique<voxcpm::VoxCPMServiceCore>(model_path, voxcpm::BackendType::Vulkan,
                                                               threads);
        g_e.core->load();
        g_e.sample_rate = g_e.core->sample_rate();
        if (!g_e.voices_dir.empty()) {
            g_e.store = std::make_unique<voxcpm::VoiceStore>(g_e.voices_dir);
        }
    } catch (const std::exception & e) {
        std::printf("ps5mm-voxcpm: could not load %s: %s\n", model_path, e.what());
        std::fflush(nullptr);
        return -1;
    }

    g_e.status = 2;
    fail_guard.release();
    std::printf("ps5mm-voxcpm: loaded in %lld ms, %d Hz, %d threads\n",
                (long long) (now_ms() - t0), g_e.sample_rate, threads);
    std::fflush(nullptr);

    g_svr.Get("/health", on_health);
    g_svr.Post("/unload", on_unload);
    g_svr.Get("/v1/audio/voices", on_voices);
    g_svr.Post("/v1/audio/speech", on_speech);
    g_svr.set_read_timeout(60, 0);
    g_svr.set_write_timeout(600, 0);
    g_svr.set_payload_max_length(4 * 1024 * 1024);

    g_thread = std::thread([port] {
        if (!g_svr.listen("0.0.0.0", port)) {
            std::printf("ps5mm-voxcpm: could not listen on %d\n", port);
            std::fflush(nullptr);
        }
        std::printf("ps5mm-voxcpm: the listener stopped\n");
        std::fflush(nullptr);
    });
    return 0;
}

void voxcpm_server_terminate(void) {
    if (g_stop.exchange(true)) {
        return;
    }
    g_svr.stop();
    if (g_thread.joinable()) {
        g_thread.join();
    }
}

bool voxcpm_server_ready(void) {
    return g_e.core && g_e.core->loaded();
}

int voxcpm_server_status(void) {
    return g_e.status.load();
}

bool voxcpm_server_busy(void) {
    return g_e.busy.load();
}

long voxcpm_server_requests(void) {
    return g_e.requests.load();
}

std::string voxcpm_server_state(void) {
    char buf[512];
    std::snprintf(buf, sizeof buf, "model=%s voices=%s rate=%d requests=%ld",
                  g_e.model_path.c_str(), g_e.voices_dir.c_str(), g_e.sample_rate,
                  g_e.requests.load());
    return std::string(buf);
}
