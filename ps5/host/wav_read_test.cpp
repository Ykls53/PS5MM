// Unit check for the hand-written PCM16 WAV reader that now feeds qwen3's voice
// reference. Same code as audio_server.cpp -- copied here so it can run without
// audio.cpp's C API.
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

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
    int                format = 0, bits = 0;
    std::vector<char>  data;
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

int main(int argc, char ** argv) {
    const char * path = argc > 1 ? argv[1] : "/tmp/tts-short1.wav";
    std::vector<float> pcm;
    int                rate = 0, ch = 0;
    const bool         ok   = read_wav_pcm16(path, pcm, rate, ch);
    std::printf("read=%d rate=%d ch=%d samples=%zu\n", (int) ok, rate, ch, pcm.size());
    if (!ok) {
        return 1;
    }
    double sum = 0, peak = 0;
    for (float v : pcm) {
        sum += (double) v * v;
        if (std::fabs(v) > peak) {
            peak = std::fabs(v);
        }
    }
    const double rms = pcm.empty() ? 0 : std::sqrt(sum / (double) pcm.size());
    std::printf("duration=%.2fs rms=%.4f peak=%.4f\n", (double) (pcm.size() / (size_t) ch) / rate, rms, peak);
    return 0;
}
