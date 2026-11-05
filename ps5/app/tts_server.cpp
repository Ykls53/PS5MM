// SPDX-License-Identifier: GPL-3.0-or-later
// PS5MM's speech engine: Qwen3-TTS voice cloning behind OpenAI's
// /v1/audio/speech, in the same process as the text and image engines.
//
// The reference voice is a WAV (or mp3, flac) file in <voices_dir>/; its name
// is the request's "voice". With no reference the model still speaks, in its
// own voice: llama.cpp clones a speaker embedding taken from that file.
//
// One backbone GGUF (the talker) and one mmproj GGUF (the codec), loaded once.
// Requests are serialised: there is one context and one KV cache, and a voice
// request is short compared with the images next door.

#include "tts_server.hpp"

#include "llama.h"
#include "mtmd.h"
#include "mtmd-helper.h"

#include "ggml-backend.h"   // ggml_backend_dev_by_type(): is there a GPU at all?

#include "cpp-httplib/httplib.h"
#include "nlohmann/json.hpp"

#include <dirent.h>
#include <sys/stat.h>

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace {

using json = nlohmann::json;

// Long text is cut at this many frames rather than spoken for minutes: at
// 12 Hz that is well over two minutes of audio.
constexpr int kMaxFrames   = 2048;
constexpr int kPromptBatch = 512;

struct Engine {
    llama_model *     model       = nullptr;
    llama_context *   lctx        = nullptr;
    mtmd_context *    mctx        = nullptr;
    int32_t           sample_rate = 0;
    bool              ready       = false;
    std::string       backbone;
    std::string       mmproj;
    std::string       voices;
    std::atomic<long> requests{ 0 };
    // 0 尚未开始（没配置模型），1 加载中，2 就绪，-1 加载失败：界面的槽位状态靠它，
    // 不然只能看 ready 一直 false，分不清「还在加载」和「已经死了」。
    std::atomic<int>  status{ 0 };
    std::atomic<bool> busy{ false };   // 正在合成一句话
    std::mutex        mu;   // one generation at a time: one context, one KV
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

// The reference file for a request's "voice": a name in the voices folder, or
// an absolute path. Names cannot climb out of the folder.
std::string voice_path(const std::string & voice) {
    if (voice.empty()) {
        return std::string();
    }
    if (voice[0] == '/') {
        return voice;
    }
    if (voice.find("..") != std::string::npos) {
        return std::string();
    }
    return g_e.voices + "/" + voice;
}

// Speaks text and returns a WAV file in wav. Holds the engine lock.
bool synthesize(const std::string & text, const std::string & voice, const std::string & lang,
                int top_k, float top_p, uint32_t seed, std::string & wav, std::string & err) {
    std::lock_guard<std::mutex> lock(g_e.mu);
    if (!g_e.ready) {
        err = "the speech model is not loaded";
        return false;
    }
    g_e.busy = true;
    const auto done = [](void *) { g_e.busy = false; };
    std::unique_ptr<void, decltype(done)> busy_guard(reinterpret_cast<void *>(1), done);
    // The last request's tokens must go, or this one continues its sentence.
    llama_memory_clear(llama_get_memory(g_e.lctx), true);

    mtmd_helper::gen_audio gen(g_e.lctx, g_e.mctx);
    if (!gen.ctx) {
        err = "could not start the audio generator";
        return false;
    }

    mtmd::bitmap_ptr speaker;
    const std::string ref = voice_path(voice);
    if (!ref.empty()) {
        auto wrapper = mtmd_helper_bitmap_init_from_file(g_e.mctx, ref.c_str(), false, mtmd_helper_init_opt_default());
        if (wrapper.bitmap != nullptr) {
            speaker.reset(wrapper.bitmap);
        } else {
            std::printf("ps5mm-tts: could not read the reference %s; speaking without it\n", ref.c_str());
        }
    }

    mtmd_helper_gen_audio_inp inp{};
    inp.seq_id      = 0;
    inp.prompt      = text.c_str();
    inp.prompt_len  = text.size();
    inp.speaker_ref = speaker.get();
    inp.lang        = lang.empty() ? "zh" : lang.c_str();
    inp.top_k       = top_k;
    inp.top_p       = top_p;
    inp.seed        = seed;
    inp.out_type    = MTMD_HELPER_GEN_AUDIO_OUTTYPE_WAV;

    const int64_t t0 = ggml_time_ms();
    if (gen.set_input(&inp) != 0) {
        err = "the prompt was refused";
        return false;
    }
    for (;;) {
        const int32_t left = gen.step_prompt(kPromptBatch);
        if (left < 0) {
            err = "prompt processing failed";
            return false;
        }
        if (left == 0) {
            break;
        }
    }

    llama_sampler_chain_params sparams = llama_sampler_chain_default_params();
    llama_sampler *           smpl     = llama_sampler_chain_init(sparams);
    llama_sampler_chain_add(smpl, llama_sampler_init_top_k(top_k));
    llama_sampler_chain_add(smpl, llama_sampler_init_top_p(top_p, 1));
    llama_sampler_chain_add(smpl, llama_sampler_init_temp(0.9f));
    llama_sampler_chain_add(smpl, llama_sampler_init_dist(seed));

    int           frames  = 0;
    bool          stop    = false;
    llama_token   sampled = llama_sampler_sample(smpl, g_e.lctx, -1);
    const float * h       = llama_get_embeddings_ith(g_e.lctx, -1);
    while (!stop && frames < kMaxFrames) {
        const float * h_next = nullptr;
        if (gen.step_gen(sampled, h, &h_next, &stop) != 0) {
            llama_sampler_free(smpl);
            err = "generation failed";
            return false;
        }
        if (h_next == nullptr) {
            break;   // stopped without a frame
        }
        frames++;
        h       = h_next;
        sampled = llama_sampler_sample(smpl, g_e.lctx, -1);
    }
    llama_sampler_free(smpl);

    int32_t      rate = 0;
    const char * data = nullptr;
    size_t       len  = 0;
    int64_t      n    = 0;
    if (gen.get_output(&rate, &data, &len, &n) != 0 || data == nullptr || len == 0) {
        err = "no audio came out";
        return false;
    }
    wav.assign(data, len);
    std::printf("ps5mm-tts: %d frames, %d Hz, %zu bytes of wav in %lld ms\n", frames, rate, len,
                (long long) (ggml_time_ms() - t0));
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
    // "voice" is a file in the voices folder (the clone's reference), or an
    // absolute path; "lang" is zh by default.
    const std::string voice = body.value("voice", std::string());
    const std::string lang  = body.value("lang", std::string("zh"));
    const int         top_k = body.value("top_k", 50);
    const float       top_p = body.value("top_p", 0.95f);
    const uint32_t    seed  = body.value("seed", (uint32_t) LLAMA_DEFAULT_SEED);

    g_e.requests++;
    std::string wav;
    std::string err;
    if (!synthesize(text, voice, lang, top_k, top_p, seed, wav, err)) {
        std::printf("ps5mm-tts: %s\n", err.c_str());
        std::fflush(nullptr);
        res.status = 500;
        res.set_content(json{ { "error", err } }.dump(), "application/json");
        return;
    }
    res.set_content(std::move(wav), "audio/wav");
}

void on_health(const httplib::Request &, httplib::Response & res) {
    json out{ { "ok", g_e.ready }, { "engine", "tts" }, { "requests", (long) g_e.requests.load() },
              { "sample_rate", g_e.sample_rate }, { "model", g_e.backbone } };
    res.set_content(out.dump(), "application/json");
}

void on_voices(const httplib::Request &, httplib::Response & res) {
    json names = json::array();
    if (DIR * d = opendir(g_e.voices.c_str())) {
        while (dirent * e = readdir(d)) {
            const std::string n = e->d_name;
            if (n.size() > 4 && (n.rfind(".wav") == n.size() - 4 || n.rfind(".mp3") == n.size() - 4 ||
                                 n.rfind(".flac") == n.size() - 5)) {
                names.push_back(n);
            }
        }
        closedir(d);
    }
    res.set_content(json{ { "voices", names } }.dump(), "application/json");
}

}  // namespace

int tts_server_start(const char * backbone, const char * mmproj, const char * voices_dir, int port) {
    if (backbone == nullptr || mmproj == nullptr) {
        return -1;
    }
    g_e.backbone = backbone;
    g_e.mmproj   = mmproj;
    g_e.voices   = voices_dir != nullptr ? voices_dir : "";
    g_e.status   = 1;   // 加载中；下面任何一条失败路径都把它带回 -1
    // 任一 return -1 都会触发；加载成功时 dismiss()。
    auto fail_guard = std::unique_ptr<void, void (*)(void *)>(reinterpret_cast<void *>(1), [](void *) {
        g_e.status = -1;
    });

    // llama.cpp 会对 Qwen3-TTS 两千多个 codec token 逐个打一行
    //   load: control token: 153717 '<|codec_1781|>' is not marked as EOG
    // 而 stderr 是无缓冲的（main.cpp 设成 _IONBF），于是每个 token 一次 write()。
    // 实测这台机器 45 秒才走 62 个（1.4 个/秒），全程 25 分钟才轮到加载 tensor。
    // 只吞这一句和 DEBUG 级，print_info / load_tensors 照常留在 app.log 里。
    static std::atomic<bool> s_log_filter{ false };
    if (!s_log_filter.exchange(true)) {
        llama_log_set([](ggml_log_level level, const char * text, void *) {
            if (text != nullptr && std::strstr(text, "is not marked as EOG") != nullptr) {
                return;
            }
            if ((int) level >= (int) GGML_LOG_LEVEL_DEBUG) {
                return;
            }
            std::fputs(text, stderr);
        }, nullptr);
    }

    std::printf("ps5mm-tts: loading %s\n", backbone);
    std::printf("ps5mm-tts: mmproj   %s\n", mmproj);
    std::fflush(nullptr);

    const int64_t t0 = ggml_time_ms();

    llama_model_params mparams = llama_model_default_params();
    // 语音跑 CPU，不上 GPU。
    // 2026-11-05 实测：在 RADV 上跑 mtmd 的音频生成（qwen3tts_gen 投影器）会把
    // 整个进程锁死 —— 一句话的请求发出去之后，8002 / 8004 / 8005 / 8099 全部
    // HTTP 超时（TCP 还在听），主循环也停住，连 /data/PS5MM/quit 都读不到，
    // 只能长按电源。log 停在 init_audio 那一行。
    // 一句 1.7B Q4 的话在 8 核上是几十秒的量级：慢，但不会把 app 拖死。
    // 上游修好之前别开 GPU；要试验时用 PS5MM_TTS_NGL 覆盖。
    mparams.n_gpu_layers = 999;   // 基线：11-04 验收表证明 GPU 上 2.3s 出音频
    // 没有 GPU 后端的构建（PC 验证版）不能声明 GPU 层：llama 会按一个不存在的
    // 设备去算 buffer，然后 ggml_abort 把整个进程带走。PS5 有 RADV，这条不触发。
    if (ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_GPU) == nullptr) {
        mparams.n_gpu_layers = 0;
    }
    if (const char * ngl = std::getenv("PS5MM_TTS_NGL"); ngl != nullptr && ngl[0] != 0) {
        mparams.n_gpu_layers = std::atoi(ngl);
    }
    std::printf("ps5mm-tts: n_gpu_layers = %d\n", (int) mparams.n_gpu_layers);
    std::fflush(nullptr);
    g_e.model                  = llama_model_load_from_file(backbone, mparams);
    if (g_e.model == nullptr) {
        std::printf("ps5mm-tts: could not load %s\n", backbone);
        return -1;
    }

    llama_context_params cparams = llama_context_default_params();
    const unsigned hw = std::thread::hardware_concurrency();
    cparams.n_ctx      = 4096;
    cparams.n_batch    = kPromptBatch;
    cparams.n_ubatch   = 128;
    cparams.n_threads  = hw > 2 ? hw - 2 : 1;   // the title leaves the others to the system
    cparams.n_threads_batch = cparams.n_threads;
    cparams.embeddings = true;   // gen_audio takes the hidden state of each sampled token
    cparams.no_perf    = true;
    g_e.lctx           = llama_init_from_model(g_e.model, cparams);
    if (g_e.lctx == nullptr) {
        std::printf("ps5mm-tts: could not start the context\n");
        llama_model_free(g_e.model);
        g_e.model = nullptr;
        return -1;
    }

    mtmd_context_params mp = mtmd_context_params_default();
    // 投影器也不能上 GPU：只把主模型放 CPU 不够，第一次合成照样把整个进程锁死
    // （日志 clip_ctx: CLIP using Vulkan0 backend 之后 8002/8004/8005/8099 全超时）。
    mp.use_gpu             = true;
    mp.n_threads           = cparams.n_threads;
    mp.print_timings       = false;
    g_e.mctx               = mtmd_init_from_file(mmproj, g_e.model, mp);
    if (g_e.mctx == nullptr) {
        std::printf("ps5mm-tts: could not load the mmproj %s\n", mmproj);
        llama_free(g_e.lctx);
        llama_model_free(g_e.model);
        g_e.lctx  = nullptr;
        g_e.model = nullptr;
        return -1;
    }
    const mtmd_gen_audio_info info = mtmd_gen_audio_get_info(g_e.mctx);
    if (info.type == MTMD_GEN_AUDIO_TYPE_NONE) {
        std::printf("ps5mm-tts: this mmproj makes no audio; speech is off\n");
        mtmd_free(g_e.mctx);
        llama_free(g_e.lctx);
        llama_model_free(g_e.model);
        g_e.mctx  = nullptr;
        g_e.lctx  = nullptr;
        g_e.model = nullptr;
        return -1;
    }
    g_e.sample_rate = info.sample_rate;
    g_e.ready       = true;
    g_e.status      = 2;
    fail_guard.release();
    std::printf("ps5mm-tts: loaded in %lld ms, %d Hz, variant %s\n", (long long) (ggml_time_ms() - t0),
                info.sample_rate, info.model_variant != nullptr ? info.model_variant : "-");
    std::printf("ps5mm-tts: listening on :%d, voices in %s\n", port,
                g_e.voices.empty() ? "(none)" : g_e.voices.c_str());
    std::fflush(nullptr);

    g_svr.Get("/health", on_health);
    g_svr.Get("/v1/audio/voices", on_voices);
    g_svr.Post("/v1/audio/speech", on_speech);
    g_svr.set_read_timeout(60, 0);
    g_svr.set_write_timeout(600, 0);   // a long line takes a while to write out
    g_svr.set_payload_max_length(4 * 1024 * 1024);

    g_thread = std::thread([port] {
        if (!g_svr.listen("0.0.0.0", port)) {
            std::printf("ps5mm-tts: could not listen on %d\n", port);
            std::fflush(nullptr);
        }
        std::printf("ps5mm-tts: the listener stopped\n");
        std::fflush(nullptr);
    });
    return 0;
}

void tts_server_terminate(void) {
    if (g_stop.exchange(true)) {
        return;
    }
    g_svr.stop();
    if (g_thread.joinable()) {
        g_thread.join();
    }
}

bool tts_server_ready(void) {
    return g_e.ready;
}

int tts_server_status(void) {
    return g_e.status.load();
}

void tts_server_abandon(void) {
    // 配置里指了模型但文件不在：界面上别一直显示「加载中」。
    if (g_e.status.load() == 0) {
        g_e.status = -1;
    }
}

long tts_server_requests(void) {
    return g_e.requests.load();
}

bool tts_server_busy(void) {
    return g_e.busy.load();
}

std::string tts_server_state(void) {
    char buf[512];
    std::snprintf(buf, sizeof buf, "backbone=%s mmproj=%s rate=%d requests=%ld", g_e.backbone.c_str(),
                  g_e.mmproj.c_str(), g_e.sample_rate, g_e.requests.load());
    return std::string(buf);
}
