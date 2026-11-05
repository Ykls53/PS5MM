// Minimal TTS probe: call tts_server_start() directly and see where it dies.
// It listens on a throwaway port; we only care about the model load.
#include "tts_server.hpp"

#include <cstdio>
#include <cstdlib>
#include <unistd.h>

int main(int argc, char ** argv) {
    const char * backbone = argc > 1 ? argv[1] : "/data/PS5MM/tts/backbone.gguf";
    const char * mmproj   = argc > 2 ? argv[2] : "/data/PS5MM/tts/mmproj.gguf";
    const char * voices   = argc > 3 ? argv[3] : "/data/PS5MM/voices";

    std::printf("[probe] tts_server_start(%s, %s, %s, 8098)\n", backbone, mmproj, voices);
    std::fflush(stdout);
    const int rc = tts_server_start(backbone, mmproj, voices, 8098);
    std::printf("[probe] rc=%d ready=%d\n", rc, (int) tts_server_ready());
    std::fflush(stdout);
    tts_server_terminate();
    return rc == 0 ? 0 : 1;
}
