// SPDX-License-Identifier: GPL-3.0-or-later
// PS5MM on a PC: the same engines, the same ports, none of the console code.
//
// main.cpp owns the display, the pad and the dashboard. This one owns only the
// listeners, so engine behaviour (model slots, RIFE, audio, media, shutdown) can
// be exercised in seconds on x86 instead of "rebuild, transfer, restart the
// console, wait". It is a verification harness, not a product.
//
//   scripts/build-host.sh            -> build/host/ps5mm-host
//   build/host/ps5mm-host --settings /data/PS5MM/settings.json
//
// Paths are the same as on the console (/data/PS5MM/...), so one settings.json
// describes both. On a PC they are symlinked into place by scripts/setup-host.sh.

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>

#include <sys/stat.h>
#include <unistd.h>

#include "httplib.h"

#include "adaptive.hpp"
#include "audio_server.hpp"
#include "ports.hpp"
#include "sd_server.hpp"
#include "settings.hpp"
#include "trellis_server.hpp"
#include "tts_server.hpp"

namespace {

std::atomic<bool> g_quit{ false };
const char *      g_settings_path = "/data/PS5MM/settings.json";
const char *      g_outputs       = "/data/PS5MM/outputs";

void on_signal(int) {
    g_quit.store(true);
}

void say(const char * fmt, const std::string & a) {
    std::printf(fmt, a.c_str());
    std::fflush(nullptr);
}

bool exists(const std::string & p) {
    return !p.empty() && access(p.c_str(), F_OK) == 0;
}

// The first free slot after the three assigned ones, exactly like main.cpp:
// audio takes the next, 3D the one after that.
int next_free_slot(const ps5lm::Settings & s, int skip) {
    for (int i = 1; i <= ps5mm::kSlotCount; ++i) {
        if (i == s.text_slot || i == s.picture_slot || i == s.speech_slot || i == skip) {
            continue;
        }
        return i;
    }
    return 0;
}

}  // namespace

int main(int argc, char ** argv) {
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--settings") == 0 && i + 1 < argc) {
            g_settings_path = argv[++i];
        }
    }
    if (const char * e = std::getenv("PS5MM_SETTINGS"); e != nullptr && e[0] != 0) {
        g_settings_path = e;
    }

    ::signal(SIGINT, on_signal);
    ::signal(SIGTERM, on_signal);
    ::signal(SIGPIPE, SIG_IGN);

    const ps5lm::Settings s = ps5lm::load_settings(g_settings_path);
    std::printf("ps5mm-host: settings %s\n", g_settings_path);
    std::printf("ps5mm-host: slots text=%d picture=%d speech=%d\n", s.text_slot, s.picture_slot, s.speech_slot);
    std::fflush(nullptr);
    // caps() initialises ggml's backend registry. On a machine with no GPU that
    // is harmless, but it has side effects on the llama.cpp build used here, so
    // PS5MM_NO_CAPS=1 lets a run skip it while we bisect.
    if (std::getenv("PS5MM_NO_CAPS") == nullptr) {
        ps5mm::print_caps();
    }

    // ---- the speech engine, in a child process ---------------------------
    // llama.cpp answers a load failure with abort(), and an abort() takes the
    // whole process with it -- every engine, the dashboard, the quit route.
    // On the console the load succeeds (Vulkan), but the failure mode is still
    // wrong, so speech runs here as its own process: if it dies, port 8003 does
    // and nothing else.
    const bool only_tts = (argc > 1 && std::strcmp(argv[1], "--only-tts") == 0) ||
                          std::getenv("PS5MM_ONLY_TTS") != nullptr;
    if (only_tts) {
        ::signal(SIGINT, on_signal);
        ::signal(SIGTERM, on_signal);
        const int port = ps5mm::port_of_slot(s.speech_slot);
        std::printf("ps5mm-host(tts): loading on :%d\n", port);
        std::fflush(nullptr);
        if (tts_server_start(s.tts_backbone.c_str(), s.tts_mmproj.c_str(), s.voices_dir.c_str(), port) != 0) {
            std::printf("ps5mm-host(tts): the model did not load\n");
            std::fflush(nullptr);
            return 1;
        }
        while (!g_quit.load()) {
            ::usleep(200 * 1000);
        }
        tts_server_terminate();
        return 0;
    }

    ::mkdir(g_outputs, 0777);

    // ---- control port: /alive /state /quit --------------------------------
    httplib::Server ctl;
    ctl.Get("/alive", [](const httplib::Request &, httplib::Response & res) {
        res.set_content("ps5mm-host alive\n", "text/plain");
    });
    ctl.Get("/state", [](const httplib::Request &, httplib::Response & res) {
        std::string out = "sd=" + sd_server_state() + "\n";
        out += "tts=" + tts_server_state() + "\n";
#ifdef PS5MM_HOST_AUDIO
        out += "audio=" + audio_server_family() + "\n";
#endif
        res.set_content(out, "text/plain");
    });
    ctl.Post("/quit", [](const httplib::Request &, httplib::Response & res) {
        res.set_content("ps5mm-host: quitting\n", "text/plain");
        g_quit.store(true);
    });
    const int ctl_port = 8099;
    std::thread([&ctl, ctl_port] {
        if (!ctl.listen("0.0.0.0", ctl_port)) {
            std::printf("ps5mm-host: control port %d busy\n", ctl_port);
            std::fflush(nullptr);
        }
    }).detach();

    // ---- the speech engine (its own binary, see above) --------------------
    pid_t tts_pid = -1;
    if (!s.tts_backbone.empty() && exists(s.tts_backbone) && exists(s.tts_mmproj)) {
        // A sibling binary next to this one: ps5mm-tts links llama.cpp only.
        char    exe[4096];
        ssize_t n = ::readlink("/proc/self/exe", exe, sizeof exe - 1);
        std::string tts_bin = "./ps5mm-tts";
        if (n > 0) {
            exe[n]    = 0;
            std::string self(exe);
            tts_bin = self.substr(0, self.find_last_of('/') + 1) + "ps5mm-tts";
        }
        tts_pid = ::fork();
        if (tts_pid == 0) {
            ::execl(tts_bin.c_str(), "ps5mm-tts", "--settings", g_settings_path,
                    static_cast<char *>(nullptr));
            ::_exit(127);
        }
        std::printf("ps5mm-host: speech engine in child pid %d (%s)\n", (int) tts_pid, tts_bin.c_str());
        std::fflush(nullptr);
    } else {
        std::printf("ps5mm-host: speech engine skipped (backbone %s, mmproj %s)\n", s.tts_backbone.c_str(),
                    s.tts_mmproj.c_str());
        std::fflush(nullptr);
        tts_server_abandon();
    }

    // ---- the audio engine -------------------------------------------------
    const int audio_slot = next_free_slot(s, 0);
#ifdef PS5MM_HOST_AUDIO
    if (audio_slot != 0) {
        const int audio_port = ps5mm::port_of_slot(audio_slot);
        std::thread([&s, audio_port] {
            AudioModels m{ s.audio_model.c_str(), "tts", s.audio_dir.c_str() };
            std::printf("ps5mm-host: audio engine on :%d (loads on first request)\n", audio_port);
            std::fflush(nullptr);
            if (audio_server_start(m, audio_port) != 0) {
                std::printf("ps5mm-host: audio listener failed on :%d\n", audio_port);
                std::fflush(nullptr);
            }
        }).detach();
    }
#else
    (void) audio_slot;
    std::printf("ps5mm-host: audio engine not built in (no audiocpp C API)\n");
    std::fflush(nullptr);
#endif

    // ---- the 3D engine ----------------------------------------------------
    const int slot3d = next_free_slot(s, audio_slot);
#ifdef PS5MM_HOST_TRELLIS
    if (slot3d != 0 && exists(s.trellis_dir)) {
        const int p3d = ps5mm::port_of_slot(slot3d);
        std::thread([&s, p3d] {
            TrellisPaths paths{ s.trellis_dir.c_str(), g_outputs, nullptr };
            std::printf("ps5mm-host: 3D engine on :%d\n", p3d);
            std::fflush(nullptr);
            if (trellis_server_start(paths, p3d) != 0) {
                std::printf("ps5mm-host: 3D listener failed on :%d\n", p3d);
                std::fflush(nullptr);
            }
        }).detach();
    } else {
        std::printf("ps5mm-host: 3D engine skipped (%s)\n", s.trellis_dir.c_str());
        std::fflush(nullptr);
    }
#else
    (void) slot3d;
#endif

    // ---- the picture engine (media + interp ride on its port) -------------
    {
        const int p = ps5mm::port_of_slot(s.picture_slot);
        SdModels models{ nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, g_outputs,
                         nullptr, nullptr, nullptr };
        static std::string diffusion, clip_l, clip_g, t5xxl, vae, esrgan;
        static std::string video, video_t5xxl, video_vae;
        diffusion = s.sd_diffusion;
        clip_l    = s.sd_clip_l;
        clip_g    = s.sd_clip_g;
        t5xxl     = s.sd_t5xxl;
        vae       = s.sd_vae;
        esrgan    = s.sd_esrgan;
        video        = s.sd_video;
        video_t5xxl  = s.sd_video_t5xxl.empty() ? s.sd_t5xxl : s.sd_video_t5xxl;
        video_vae    = s.sd_video_vae.empty() ? s.sd_vae : s.sd_video_vae;
        models.diffusion = diffusion.empty() ? nullptr : diffusion.c_str();
        models.clip_l    = clip_l.empty() ? nullptr : clip_l.c_str();
        models.clip_g    = clip_g.empty() ? nullptr : clip_g.c_str();
        models.t5xxl     = t5xxl.empty() ? nullptr : t5xxl.c_str();
        models.vae       = vae.empty() ? nullptr : vae.c_str();
        models.esrgan    = esrgan.empty() ? nullptr : esrgan.c_str();
        models.video_diffusion = video.empty() ? nullptr : video.c_str();
        models.video_t5xxl     = video_t5xxl.empty() ? nullptr : video_t5xxl.c_str();
        models.video_vae       = video_vae.empty() ? nullptr : video_vae.c_str();
        std::printf("ps5mm-host: picture engine on :%d (loads on first request)\n", p);
        std::fflush(nullptr);
        if (sd_server_start(models, p) != 0) {
            std::printf("ps5mm-host: picture listener failed on :%d\n", p);
            std::fflush(nullptr);
        }
    }

    while (!g_quit.load()) {
        ::usleep(200 * 1000);
    }

    std::printf("ps5mm-host: quitting\n");
    std::fflush(nullptr);
    sd_server_terminate();
    if (tts_pid > 0) {
        ::kill(tts_pid, SIGTERM);   // the child owns port 8003; ask it to go
    }
#ifdef PS5MM_HOST_AUDIO
    audio_server_terminate();
#endif
#ifdef PS5MM_HOST_TRELLIS
    trellis_server_terminate();
#endif
    ctl.stop();
    std::printf("ps5mm-host: bye\n");
    std::fflush(nullptr);
    return 0;
}
