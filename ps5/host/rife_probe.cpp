// Standalone RIFE probe: does load() or process() crash, and where?
// Built by scripts/host-rife-probe.sh; run under gdb when it dies.
#include "rife.h"

#include <cstdio>
#include <vector>

int main(int argc, char ** argv) {
    const char * dir = argc > 1 ? argv[1] : "/data/PS5MM/rife";
    const int    w   = 64, h = 64;

    std::printf("[probe] RIFE(-1, ...) construction\n");
    std::fflush(stdout);
    RIFE r(-1, false, false, false, 4, false, true);

    std::printf("[probe] load %s\n", dir);
    std::fflush(stdout);
    const int rc = r.load(dir);
    std::printf("[probe] load rc=%d\n", rc);
    std::fflush(stdout);
    if (rc != 0) {
        return 1;
    }

    std::vector<unsigned char> pa((size_t) w * h * 3), pb((size_t) w * h * 3);
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            for (int c = 0; c < 3; ++c) {
                pa[((size_t) y * w + x) * 3 + c] = (unsigned char) ((x + c * 40) & 0xff);
                pb[((size_t) y * w + x) * 3 + c] = (unsigned char) (((w - x) + c * 40) & 0xff);
            }
        }
    }
    const ncnn::Mat a = ncnn::Mat::from_pixels(pa.data(), ncnn::Mat::PIXEL_RGB, w, h);
    const ncnn::Mat b = ncnn::Mat::from_pixels(pb.data(), ncnn::Mat::PIXEL_RGB, w, h);

    ncnn::Mat out;
    std::printf("[probe] process\n");
    std::fflush(stdout);
    const int prc = r.process(a, b, 0.5f, out);
    std::printf("[probe] process rc=%d out=%d x %d x %d\n", prc, out.w, out.h, out.c);
    std::fflush(stdout);
    return prc == 0 ? 0 : 2;
}
