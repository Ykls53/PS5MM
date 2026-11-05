// The speech engine as its own binary: llama.cpp and nothing else.
//
// Why not inside ps5mm-host? With stable-diffusion's ggml and ncnn linked into
// the same image, llama_model_load_from_file() aborts (ggml_tallocr_alloc:
// "not enough space in the buffer") even with n_gpu_layers = 0, and an abort
// kills every engine in the process. A separate image loads the same model
// cleanly -- that is what the standalone probe proved.
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unistd.h>

#include "ports.hpp"
#include "settings.hpp"
#include "tts_server.hpp"

namespace {
volatile std::sig_atomic_t g_stop = 0;
void on_signal(int) { g_stop = 1; }
}  // namespace

int main(int argc, char ** argv) {
    const char * settings_path = "/data/PS5MM/settings.json";
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--settings") == 0 && i + 1 < argc) {
            settings_path = argv[++i];
        }
    }
    ::signal(SIGINT, on_signal);
    ::signal(SIGTERM, on_signal);

    const ps5lm::Settings s = ps5lm::load_settings(settings_path);
    const int port = ps5mm::port_of_slot(s.speech_slot);
    std::printf("ps5mm-tts: backbone %s\n", s.tts_backbone.c_str());
    std::fflush(nullptr);
    if (tts_server_start(s.tts_backbone.c_str(), s.tts_mmproj.c_str(), s.voices_dir.c_str(), port) != 0) {
        std::printf("ps5mm-tts: the model did not load\n");
        std::fflush(nullptr);
        return 1;
    }
    while (!g_stop) {
        ::usleep(200 * 1000);
    }
    tts_server_terminate();
    return 0;
}
