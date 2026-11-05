// Does ncnn see a Vulkan device on this machine? Prints the count and the name
// without creating a RIFE instance, so it isolates the "init Vulkan" step from
// "load the flow net".
#include "gpu.h"

#include <cstdio>

int main() {
    std::printf("[ncnn] get_gpu_count() ...\n");
    std::fflush(stdout);
    const int n = ncnn::get_gpu_count();
    std::printf("[ncnn] gpu_count = %d\n", n);
    for (int i = 0; i < n; ++i) {
        const ncnn::GpuInfo & info = ncnn::get_gpu_info(i);
        std::printf("[ncnn] gpu[%d] = %s api=%u\n", i, info.device_name(), (unsigned) info.api_version());
    }
    std::fflush(stdout);
    return 0;
}
