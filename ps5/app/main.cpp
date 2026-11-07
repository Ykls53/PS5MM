// PS5LM native app: llama-server on the PS5's GPU through RADV (ggml-vulkan),
// with a dashboard on the TV drawn by ps5-homebrew-ui through ps5-opengl.
//
// A title gets the console's direct memory (12 GiB) where a payload gets none,
// and RADV turns it into Vulkan device memory, so the whole model sits on the
// GPU. llama-server runs on its own thread on port 8081 (chat page and OpenAI
// API); the main thread draws the dashboard, reads the controller and plays
// the interface sounds. Models come from /data/PS5MM/models and USB drives; the
// planner (model_plan.cpp) picks each one's context and cache for the memory
// free. /data/PS5MM/app-args.txt, one argument per line, overrides all of it.
// The app logs to /data/PS5MM/app.log and llama.log.
//
// SPDX-License-Identifier: GPL-3.0-or-later

#include <pthread.h>
#include <fcntl.h>
#include <dirent.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <filesystem>
#include <fstream>
#include <functional>
#include <mutex>
#include <span>
#include <string>
#include <thread>
#include <vector>

#include "tts_server.hpp"
#include "voxcpm_server.hpp"
#include "sd_server.hpp"
// 退出通道要起一个自己的 listener，用的就是各引擎那份 httplib。
// 链接时它早就在了，这里只是把这个头引进当前 translation unit。
#include "cpp-httplib/httplib.h"
#include "ports.hpp"

#include <vulkan/vulkan_core.h>

#include <GL/glcorearb.h>

#include "dashboard.hpp"
#include "fetch.hpp"
#include "market.hpp"
#include "display.hpp"
#include "ggml-backend.h"
#include "model_plan.hpp"
#include "settings.hpp"
#include "adaptive.hpp"
#include "stats.hpp"
#include "suggested.hpp"
#include "version.hpp"

#include <ps5platform/heap.h>
#include <ps5platform/kernel.h>

#include "audio/mixer.hpp"
#include "core/input.hpp"
#include "core/save_file.hpp"
#include "gfx/renderer.hpp"
#include "platform/ps5/audio_out.hpp"
#include "platform/ps5/pad.hpp"
#include "platform/ps5/system.hpp"
#include "ui/fonts.hpp"
#include "trellis_server.hpp"

int  llama_server(int argc, char ** argv);
void llama_server_terminate();

// ---- Vulkan without a loader ----------------------------------------------------
// RADV is linked in whole, and ggml-vulkan's dispatcher starts from
// vkGetInstanceProcAddr, which the ICD entry point answers for every command.
// The few commands ggml calls by name go to Mesa's common implementations,
// which dispatch through the object's own table.
extern "C" PFN_vkVoidFunction vk_icdGetInstanceProcAddr(VkInstance instance, const char * name);
extern "C" PFN_vkVoidFunction vkGetInstanceProcAddr(VkInstance instance, const char * name) {
    return vk_icdGetInstanceProcAddr(instance, name);
}
extern "C" PFN_vkVoidFunction vk_common_GetDeviceProcAddr(VkDevice device, const char * name);
extern "C" void vk_common_GetPhysicalDeviceFeatures2(VkPhysicalDevice dev, VkPhysicalDeviceFeatures2 * features);
extern "C" void vk_common_CmdCopyBuffer(VkCommandBuffer cmd, VkBuffer src, VkBuffer dst, uint32_t n,
                                        const VkBufferCopy * regions);
extern "C" PFN_vkVoidFunction vkGetDeviceProcAddr(VkDevice device, const char * name) {
    return vk_common_GetDeviceProcAddr(device, name);
}
extern "C" void vkGetPhysicalDeviceFeatures2(VkPhysicalDevice dev, VkPhysicalDeviceFeatures2 * features) {
    vk_common_GetPhysicalDeviceFeatures2(dev, features);
}
extern "C" void vkCmdCopyBuffer(VkCommandBuffer cmd, VkBuffer src, VkBuffer dst, uint32_t n,
                                const VkBufferCopy * regions) {
    vk_common_CmdCopyBuffer(cmd, src, dst, n, regions);
}

extern "C" {
int sceSystemServiceHideSplashScreen(void);
int sceKernelSendNotificationRequest(uint32_t device, void * request, size_t size, int blocking);
int sceKernelUsleep(uint32_t microseconds);
int sceSystemServiceLoadExec(const char * path, const char * const * args);
}

namespace {

using namespace ps5lm;

constexpr const char * kLog         = "/data/PS5MM/app.log";
constexpr const char * kArgs        = "/data/PS5MM/app-args.txt";
constexpr const char * kChoice      = "/data/PS5MM/model.txt";
constexpr const char * kEnv         = "/data/PS5MM/env.txt";  // driver and ggml switches, for measuring
constexpr const char * kTextOnly    = "/data/PS5MM/text-only";  // the last load's projector failed: load without it once
constexpr const char * kQuit        = "/data/PS5MM/quit";
constexpr const char * kSettings    = "/data/PS5MM/settings.json";
constexpr const char * kScratch     = "/data/PS5MM/scratch";
// The file tools only: a title cannot start processes (no shell command).
constexpr const char * kTools       = "read_file,write_file,edit_file,file_glob_search,grep_search,get_info";
constexpr const char * kLlamaLog    = "/data/PS5MM/llama.log";
constexpr const char * kModels      = "/data/PS5MM/models";
constexpr const char * kAssets      = "/app0/assets";
// Ports come in the order the engines start: see ports.hpp.
// 语音引擎：Qwen3-TTS 的 backbone 与 mmproj，一个端口给 OpenAI 的 /v1/audio/speech。
constexpr const char * kTtsBackbone = "/data/PS5MM/tts/backbone.gguf";
constexpr const char * kTtsMmproj   = "/data/PS5MM/tts/mmproj.gguf";
constexpr const char * kVoices      = "/data/PS5MM/voices";
// The image engine: stable-diffusion.cpp, its own models, one port for A1111's
// /sdapi/v1/txt2img and OpenAI's /v1/images/generations.
// The picture engine reads the models PS5SD already has, without touching them:
// Wan 2.2 TI2V 5B (diffusion + text encoder + VAE), or any other the setting names.
constexpr const char * kSdModel = "/data/PS5SD/models/diffusion_models/Wan2.2-TI2V-5B-Q8_0.gguf";
constexpr const char * kSdClipL = "/data/PS5MM/sd/clip_l.safetensors";
constexpr const char * kSdClipG = "/data/PS5MM/sd/clip_g.safetensors";
constexpr const char * kSdT5    = "/data/PS5SD/models/text_encoders/umt5-xxl-encoder-Q4_K_M.gguf";
constexpr const char * kSdVae   = "/data/PS5SD/models/vae/wan2.2_vae.safetensors";
constexpr const char * kSdEsrgan = "/data/PS5MM/sd/esrgan.pth";
constexpr const char * kOutputs = "/data/PS5MM/outputs";
// Where the model library looks. PS5SD's folders are read, never written: the
// picture engine's Wan pieces already live there and duplicating 10 GB is silly.
const std::vector<std::string> kModelDirs = {
    kModels,
    "/data/PS5SD/models/diffusion_models",
    "/data/PS5SD/models/text_encoders",
    "/data/PS5SD/models/vae",
    "/mnt/ext0/PS5LM/models",
    "/mnt/usb0/PS5LM/models",
    "/mnt/usb1/PS5LM/models",
    "/mnt/usb0",
    "/mnt/usb1",
};

// The last lines of a log, up to about 64 KiB of it, oldest first.
std::vector<std::string> tail_lines(const char * path) {
    std::vector<std::string> lines;
    FILE * f = std::fopen(path, "rb");
    if (!f) {
        return lines;
    }
    std::fseek(f, 0, SEEK_END);
    const long size = std::ftell(f);
    const long from = std::max(0L, size - 65536L);
    std::fseek(f, from, SEEK_SET);
    std::string text((size_t) (size - from), '\0');
    text.resize(std::fread(text.data(), 1, text.size(), f));
    std::fclose(f);
    size_t start = from > 0 ? text.find('\n') + 1 : 0;  // the first line is cut
    for (size_t end; start < text.size() && (end = text.find('\n', start)) != std::string::npos; start = end + 1) {
        lines.emplace_back(text, start, end - start);
    }
    return lines;
}

// Probe: download a URL over HTTPS to /data/PS5MM/fetch.out, logging the
// status, size and speed (scripts/ps5lm-app.sh fetch <url>).
void probe_fetch(std::string url) {
    FILE * out = std::fopen("/data/PS5MM/fetch.out", "wb");
    const FetchResult r = https_get(url, "", [&](const char * p, size_t n) { return out && std::fwrite(p, 1, n, out) == n; });
    if (out) {
        std::fclose(out);
    }
    std::printf("ps5lm-app: fetch %s: status %d, length %lld, %llu bytes in %.1f s (%.2f MB/s)%s%s\n", url.c_str(),
                r.status, (long long) r.length, (unsigned long long) r.bytes, r.seconds,
                r.seconds > 0 ? r.bytes / 1e6 / r.seconds : 0.0, r.error.empty() ? "" : ", ", r.error.c_str());
}

// Probe: how fast the app can write, by method and place, fsync included
// (scripts/ps5lm-app.sh bench-write). 128 MiB each.
void probe_write() {
    const size_t total = 128u << 20;
    std::vector<char> buf(8u << 20, 'x');
    const char * dirs[] = { "/data/PS5MM", "/mnt/usb0" };
    for (const char * dir : dirs) {
        struct statvfs v = {};
        if (statvfs(dir, &v) != 0) {
            continue;
        }
        const std::string path = std::string(dir) + "/write-bench.tmp";
        struct Method {
            const char * name;
            size_t       chunk;
            bool         stdio;
            int          flags;
        } methods[] = {
            { "stdio 8M", 8u << 20, true, 0 },
            { "write 1M", 1u << 20, false, 0 },
            { "write 8M", 8u << 20, false, 0 },
            { "write 8M direct", 8u << 20, false, O_DIRECT },
        };
        for (const auto & m : methods) {
            const auto t0 = std::chrono::steady_clock::now();
            bool ok = true;
            if (m.stdio) {
                FILE * f = std::fopen(path.c_str(), "wb");
                for (size_t done = 0; f && ok && done < total; done += m.chunk) {
                    ok = std::fwrite(buf.data(), 1, m.chunk, f) == m.chunk;
                }
                ok = f && ok && std::fflush(f) == 0 && fsync(fileno(f)) == 0;
                if (f) {
                    std::fclose(f);
                }
            } else {
                const int fd = open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC | m.flags, 0666);
                for (size_t done = 0; fd >= 0 && ok && done < total; done += m.chunk) {
                    ok = write(fd, buf.data(), m.chunk) == (ssize_t) m.chunk;
                }
                ok = fd >= 0 && ok && fsync(fd) == 0;
                if (fd >= 0) {
                    close(fd);
                }
            }
            const double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
            std::printf("ps5lm-app: write-bench %s %s: %s, %.1f MB/s\n", dir, m.name, ok ? "ok" : strerror(errno),
                        ok ? total / 1e6 / s : 0.0);
            unlink(path.c_str());
        }
    }
    std::printf("ps5lm-app: write-bench done\n");
}

// Bytes under a folder, or 0.
uint64_t folder_bytes(const char * path) {
    std::error_code ec;
    uint64_t total = 0;
    for (auto it = std::filesystem::recursive_directory_iterator(path, ec);
         !ec && it != std::filesystem::recursive_directory_iterator(); it.increment(ec)) {
        if (it->is_regular_file(ec)) {
            total += it->file_size(ec);
        }
    }
    return total;
}

// A system notification on the TV.
void notify(const char * text) {
    struct {
        uint8_t reserved[45];
        char    message[3075];
    } request = {};
    std::snprintf(request.message, sizeof(request.message), "%s", text);
    sceKernelSendNotificationRequest(0, &request, sizeof(request), 0);
}

// A title sees only its own /app0 and /download0; /data is the HEN's to open.
// etaHEN opens it before the title starts; OnionHEN opens it on request,
// {"PID":n} in /download0/etahen_jailbreak, for a title on its app jailbreak
// allowlist. Every process asks, since the restart for a model (LoadExec)
// starts a new one, sandboxed again (#16, #23; from @abhi245y's PS5LM Plus).
// Open means the models folder lists and a file can be written there.
bool data_open() {
    mkdir("/data/PS5MM", 0777);
    mkdir(kModels, 0777);
    DIR * d = opendir(kModels);
    if (!d) {
        return false;
    }
    closedir(d);
    const int fd = open("/data/PS5MM/.probe", O_WRONLY | O_CREAT | O_TRUNC, 0666);
    if (fd < 0) {
        return false;
    }
    const bool ok = write(fd, "1", 1) == 1;
    close(fd);
    unlink("/data/PS5MM/.probe");
    return ok;
}

// How /data ended up, for the log. A refusal is remembered in /download0:
// the next starts (one per model change) still ask, but wait 2 s, not 10.
std::string open_data() {
    constexpr const char * kRefused = "/download0/PS5LM/data-closed";
    if (data_open()) {
        unlink(kRefused);
        return "open";
    }
    const int err = errno;
    const bool again = access(kRefused, F_OK) == 0;
    std::ofstream("/download0/etahen_jailbreak.tmp") << "{\"PID\":" << getpid() << "}\n";
    rename("/download0/etahen_jailbreak.tmp", "/download0/etahen_jailbreak");
    for (int i = 1; i <= (again ? 8 : 40); i++) {  // OnionHEN answered in about 3 s
        sceKernelUsleep(250000);
        if (data_open()) {
            unlink(kRefused);
            return "opened by the HEN after " + std::to_string(i / 4.0).substr(0, 4) + " s";
        }
    }
    mkdir("/download0/PS5LM", 0777);
    std::ofstream(kRefused) << "1\n";
    return std::string("closed (") + strerror(err) + "), the HEN did not open it";
}

// ---- 退出到主屏：LoadExec 可能既不返回也不退出 -------------------------------
// 2026-11-04 现场：terminate 三步全打完（tts listener stopped、sd detach），
// app 却还在画、手柄全死、PS 键被挡 —— 主线程卡在 LoadExec 里，系统等它让出
// display plane，它等系统放行。谁都动不了，只能长按电源。
// 所以退出要有人兜底：8 秒还没结束这个进程就直接结束。正常路径几毫秒就退了，
// 看门狗根本轮不到触发。
void exit_to_home(void) {
    // 先把电视还回去，再请系统收这个 title。
    // 顺序反了就是本轮那个现场：LoadExec 等系统回收 display plane，系统等
    // title 放开 surface，谁也不动，8 秒后 _exit(0) 硬杀 —— 进程没了，
    // 平面还挂着，画面冻在最后一帧。
    display_shutdown();
    std::thread([] {
        usleep(8 * 1000 * 1000);
        std::printf("ps5mm-exit: LoadExec did not end us in 8 s; hard exit\n");
        std::fflush(nullptr);
        // 硬退之前再确认一次电视已经还回去了：正常路径若卡在 eglTerminate
        // 里面，这里就是最后的机会。display_shutdown 是幂等的。
        display_shutdown();
        _exit(0);
    }).detach();
    const int rc = sceSystemServiceLoadExec("exit", nullptr);
    std::printf("ps5mm-exit: LoadExec(\"exit\") returned %d\n", rc);
    std::fflush(nullptr);
    // 能走到这一行，说明系统根本不接这次请求：与其把 title 挂在半死状态，
    // 不如自己结束进程，让系统回收 display plane。
    _exit(0);
}

// ---- 不依赖 FTP 的退出口：POST /quit + GET /alive on 8099 ----------------------
// 加载大模型时存储带宽会被吃满，FTP 整个超时（实测 25~30 秒 0 字节），
// /data/PS5MM/quit 传不进去；Options 两次那条路万一卡在某个 terminate 里，
// 也没有第二条退路。所以退出要有一个走 HTTP、不碰存储、不碰引擎的入口。
//
// 它起在 main() 很早的地方，两个路由都不加载任何东西：引擎正在啃模型的时候
// 它照样答得上来 —— 不持 g_e.mu，也不在那个被卡住的线程池里。
constexpr int kExitPort = 8099;

void exit_the_app(const char * why) {
    std::printf("ps5mm-exit: %s\n", why);
    std::fflush(nullptr);
    tts_server_terminate();
    voxcpm_server_terminate();
    sd_server_terminate();
    std::fflush(nullptr);
    exit_to_home();
}

void exit_listener_start(void) {
    static std::atomic<bool> started{ false };
    if (started.exchange(true)) {
        return;
    }
    std::thread([] {
        httplib::Server svr;
        // 探活：一行字就够，别学 ShadowMount 吐几百 KB 的网页。
        svr.Get("/alive", [](const httplib::Request &, httplib::Response & res) {
            res.set_content("ps5mm alive\n", "text/plain");
        });
        svr.Post("/quit", [](const httplib::Request &, httplib::Response & res) {
            // 先把话说出口再退：handler 自己就在这个 server 的线程池里，
            // 直接在它里面调 terminate 会把这条响应一起卡掉。
            res.set_content("ps5mm: quitting\n", "text/plain");
            std::thread([] {
                usleep(200 * 1000);   // 留出时间让响应真的发出去
                exit_the_app("HTTP /quit");
            }).detach();
        });
        // 短超时：卡住不动的客户端不许占着线程池。
        svr.set_read_timeout(5, 0);
        svr.set_write_timeout(10, 0);
        if (!svr.listen("0.0.0.0", kExitPort)) {
            std::printf("ps5mm-exit: could not listen on %d\n", kExitPort);
            std::fflush(nullptr);
            return;
        }
        std::printf("ps5mm-exit: listener stopped\n");
    }).detach();
    std::printf("ps5mm-exit: POST /quit and GET /alive on :%d\n", kExitPort);
    std::fflush(nullptr);
}

// A quit request from the PC (scripts/ps5lm-app.sh close): the app ends
// itself the way the system expects; killing a title that is rendering has
// been followed by lost consoles (ps5-homebrew-ui's AGENTS.md).
void quit_if_asked() {
    if (access(kQuit, F_OK) != 0) {
        return;
    }
    unlink(kQuit);
    std::printf("ps5lm-app: quit requested\n");
    tts_server_terminate();
    voxcpm_server_terminate();
    sd_server_terminate();
    std::fflush(nullptr);
    exit_to_home();
}

// The screen as a 24-bit BMP (glReadPixels of the TV's framebuffer), for
// checking the dashboard from the PC.
bool save_screen(const char * path, int width, int height) {
    std::vector<unsigned char> pixels((size_t) width * height * 4);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
    const uint32_t row = ((uint32_t) width * 3 + 3) & ~3u;
    const uint32_t size = 54 + row * (uint32_t) height;
    unsigned char header[54] = { 'B', 'M' };
    auto put = [&](int at, uint32_t v) {
        for (int i = 0; i < 4; ++i) {
            header[at + i] = (unsigned char) (v >> (8 * i));
        }
    };
    put(2, size);
    put(10, 54);
    put(14, 40);
    put(18, (uint32_t) width);
    put(22, (uint32_t) height);
    header[26] = 1;
    header[28] = 24;
    put(34, size - 54);
    FILE * f = std::fopen(path, "wb");
    if (!f) {
        return false;
    }
    bool ok = std::fwrite(header, 1, sizeof(header), f) == sizeof(header);
    std::vector<unsigned char> line(row);
    for (int y = 0; ok && y < height; ++y) {
        const unsigned char * in = pixels.data() + (size_t) y * width * 4;
        for (int x = 0; x < width; ++x) {
            line[(size_t) x * 3 + 0] = in[x * 4 + 2];
            line[(size_t) x * 3 + 1] = in[x * 4 + 1];
            line[(size_t) x * 3 + 2] = in[x * 4 + 0];
        }
        ok = std::fwrite(line.data(), 1, row, f) == row;
    }
    std::fclose(f);
    return ok;
}

// A request file from the PC: its first line, and the file is consumed.
std::string take_request_file(const char * path) {
    if (access(path, F_OK) != 0) {
        return {};
    }
    std::string line;
    std::ifstream(path) >> line;
    unlink(path);
    return line.empty() ? std::string("-") : line;
}

// Where the memory is: the pool's free part, the CPU heap, and what ggml
// says about each device (its GPU figure wraps once the unified heap is
// over-committed; the raw numbers still show a change).
void log_memory(const char * when) {
    int64_t at = 0;
    size_t  avail = 0;
    const int64_t pool = sceKernelGetDirectMemorySize();
    sceKernelAvailableDirectMemorySize(0, pool, 2 * 1024 * 1024, &at, &avail);
    struct ps5_heap_stats heap = {};
    ps5_heap_stats(&heap);
    std::printf("ps5lm-app: memory %s: pool free %.2f GiB, cpu heap %.2f GiB (peak %.2f)", when, avail / 1073741824.0,
                heap.mapped_bytes / 1073741824.0, heap.peak_bytes / 1073741824.0);
    for (size_t i = 0; i < ggml_backend_dev_count(); i++) {
        size_t free = 0, total = 0;
        ggml_backend_dev_memory(ggml_backend_dev_get(i), &free, &total);
        std::printf(", %s free %zu total %zu", ggml_backend_dev_name(ggml_backend_dev_get(i)), free, total);
    }
    std::printf("\n");
}

std::vector<std::string> read_lines(const char * path) {
    std::vector<std::string> out;
    std::ifstream in(path);
    for (std::string line; std::getline(in, line);) {
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) {
            line.pop_back();
        }
        if (!line.empty() && line[0] != '#') {
            out.push_back(line);
        }
    }
    return out;
}

// Free GiB on the drive whose models folder is `dir`, or -1 when unknown.
double free_gib(const std::string & dir) {
    for (const auto & d : mounted_drives()) {
        if (d.models == dir && d.total > 0) {
            return d.free;
        }
    }
    return -1;
}

std::string base_name(const std::string & path) {
    std::string n = path.substr(path.find_last_of('/') + 1);
    if (n.size() > 5 && n.compare(n.size() - 5, 5, ".gguf") == 0) {
        n.resize(n.size() - 5);
    }
    return n;
}

// ---- the server thread ------------------------------------------------------------

std::atomic<int> g_server_rc{ -1 };   // llama-server's exit code once it returns; -1 while it runs
std::atomic<bool> g_speech_voxcpm{ false };   // speech slot is served by VoxCPM, not llama.cpp
std::vector<std::string> g_server_args;

void * run_server(void *) {
    std::vector<char *> argv;
    argv.push_back(const_cast<char *>("llama-server"));
    for (auto & a : g_server_args) {
        argv.push_back(a.data());
    }
    argv.push_back(nullptr);
    int rc = 1;
    try {
        rc = llama_server((int) argv.size() - 1, argv.data());
    } catch (const std::exception & e) {
        std::printf("ps5lm-app: exception: %s\n", e.what());
    } catch (...) {
        std::printf("ps5lm-app: unknown exception\n");
    }
    std::printf("ps5lm-app: llama_server returned %d\n", rc);
    std::fflush(nullptr);
    g_server_rc = rc == 0 ? 0 : 1;
    return nullptr;
}

// ---- models -------------------------------------------------------------------------

struct Models {
    double                 budget_gib = 0;   // GPU memory free before any model
    std::vector<ModelRow>  rows;
    std::string            running;          // path of the model llama-server has
    pthread_t              server{};
    bool                   server_started = false;
    Settings               settings;

    const char * kv_force() const { return settings.kv_type == "auto" ? nullptr : settings.kv_type.c_str(); }

    void scan(StatsCollector & stats) {
        rows = plan_rows(settings, budget_gib, running);
        publish(stats);
    }

    // scan() on its own thread, for a settings change: the dashboard shows it
    // working instead of freezing while every header is read.
    std::mutex             scan_mutex;
    std::vector<ModelRow>  scanned;
    std::atomic<int>       scan_state{ 0 };  // 0 idle, 1 running, 2 done
    bool                   scan_again = false;
    bool                   scan_shown = true;  // the dashboard says it is working

    void rescan(StatsCollector & stats, bool shown = true) {
        scan_shown = shown;
        if (scan_state != 0) {
            scan_again = true;  // the running one read the old settings
            return;
        }
        scan_state = 1;
        std::thread([this, s = settings, b = budget_gib, r = running] {
            std::vector<ModelRow> out = plan_rows(s, b, r);
            std::lock_guard<std::mutex> lock(scan_mutex);
            scanned = std::move(out);
            scan_state = 2;
        }).detach();
        (void) stats;
    }

    // Takes a finished rescan; true while one is still running.
    bool poll_rescan(StatsCollector & stats) {
        if (scan_state == 2) {
            {
                std::lock_guard<std::mutex> lock(scan_mutex);
                rows = std::move(scanned);
            }
            scan_state = 0;
            publish(stats);
            if (scan_again) {
                scan_again = false;
                rescan(stats);
            }
        }
        return scan_state != 0;
    }

    static std::vector<ModelRow> plan_rows(const Settings & settings, double budget_gib, const std::string & running) {
        std::vector<ModelRow> rows;
        const char * kv = settings.kv_type == "auto" ? nullptr : settings.kv_type.c_str();
        // Also every folder the downloads can go to: the M.2 slot or a USB drive is
        // not always ext0, usb0 or usb1 (#43).
        std::vector<std::string> dirs = kModelDirs;
        std::vector<std::string> saves = { settings.download_dir };
        for (const auto & d : mounted_drives()) {
            saves.push_back(d.models);
        }
        for (const auto & d : saves) {
            if (std::find(dirs.begin(), dirs.end(), d) == dirs.end()) {
                dirs.push_back(d);
            }
        }
        // Every format the engines read, projectors included: the Settings page
        // needs to offer a codec for the speech engine and a VAE for the pictures.
        // 模型行上「由谁管」的一句话，给界面看。
        const auto kind_cn = [](const std::string & k) -> std::string {
            if (k == "speech")       return "语音";
            if (k == "video")        return "画图（视频）";
            if (k == "picture")      return "画图";
            if (k == "text-encoder") return "画图（文本编码器）";
            if (k == "vae")          return "画图（VAE）";
            if (k == "upscaler")     return "画图（放大）";
            if (k == "projector")    return "语音（codec）";
            return "各自";
        };
        for (const auto & path : find_models(dirs, true)) {
            const std::string kind = model_kind(path);
            const ModelInfo m = read_model_info(path);
            ModelRow row;
            row.file = path;
            row.label = base_name(path);
            row.drive = drive_name(path);
            struct stat st_row = {};
            const uint64_t row_bytes = m.file_bytes ? m.file_bytes
                                                     : (stat(path.c_str(), &st_row) == 0 ? (uint64_t) st_row.st_size : 0);
            row.size_gib = row_bytes / 1073741824.0;
            // 不是文字模型的（语音、画图、视频、文本编码器、放大、投影器）一律不进
            // llama.cpp 的 planner：放不放得下由各自的引擎自己算，界面也不该打「太大」。
            // 必须按 kind 判，不能按「读不读得到头」判 —— umt5 这类 GGUF 读得到头，
            // 可它是画图引擎的配件，不是能聊天的模型；塞进 planner 还会因为
            // context_length=512、档位表最小 4096 而空转，白背一个「太大」。
            if (kind != "text") {
                row.arch = kind;
                row.plan = kind_cn(kind) + "引擎直接使用";
                row.fits = true;
                row.decision = m.decision;
                row.current = path == running;
                rows.push_back(row);
                std::printf("ps5lm-app: model %s (%s, %.1f GiB): %s\n", m.file_name.c_str(), kind.c_str(),
                            row.size_gib, row.plan.c_str());
                continue;
            }
            if (!m.ok) {
                row.arch = kind;
                row.plan = m.error;
                row.fits = false;
                rows.push_back(row);
                continue;
            }
            const Plan p = plan_model(m, budget_gib, settings.ctx_cap, kv, settings.parallel_slots,
                                      ps5mm::port_of_slot(settings.text_slot));
            const Preset * pre = find_preset(m);
            row.arch = m.arch;
            row.plan = p.why;
            row.fits = p.fits;
            row.size_gib = m.file_bytes / 1073741824.0;
            row.preset = pre ? pre->label : "";
            row.decision = m.decision;
            row.current = path == running;
            rows.push_back(row);
            std::printf("ps5lm-app: model %s (%s): %s\n", m.file_name.c_str(), m.arch.c_str(), p.why.c_str());
        }
        return rows;
    }

    void publish(StatsCollector & stats) {
        std::vector<ModelRow> out = rows;
        for (auto & r : out) {
            r.current = r.file == running;
        }
        stats.set_models(out);
    }

    // The arguments for a model: the planner's, or app-args.txt's verbatim.
    std::vector<std::string> args_for(const std::string & path, Live & model_part) {
        const ModelInfo m = read_model_info(path);
        const Plan p = plan_model(m, budget_gib, settings.ctx_cap, kv_force(), settings.parallel_slots,
                                  ps5mm::port_of_slot(settings.text_slot));
        const Preset * pre = find_preset(m);
        model_part.model_label = base_name(path);
        model_part.model_file  = path;
        model_part.plan        = p.why;
        model_part.args        = p.args;
        model_part.model_arch  = m.arch;
        model_part.preset      = pre ? pre->label : "";
        model_part.decision    = m.decision;
        model_part.model_gib   = m.file_bytes / 1073741824.0;
        model_part.ctx         = p.ctx;
        model_part.kv_type     = p.kv_type;
        model_part.kv_gib      = p.kv_gib;
        return p.fits ? p.args : std::vector<std::string>{};
    }

    void start(const std::string & path, std::vector<std::string> args, StatsCollector & stats, const Live & model_part) {
        // llama.cpp's own log, written as it goes (it survives a crash), and
        // the metrics the dashboard reads.
        args.insert(args.begin(), { "--log-file", "/data/PS5MM/llama.log" });
        if (std::find(args.begin(), args.end(), "--metrics") == args.end()) {
            args.push_back("--metrics");
        }
        // The browser chat's file tools, confined to the scratch folder by
        // patches/0003 (LLAMA_TOOLS_ROOT) and working there by default.
        if (settings.tools && std::find(args.begin(), args.end(), "--tools") == args.end()) {
            std::error_code ec;
            std::filesystem::create_directories(kScratch, ec);
            setenv("LLAMA_TOOLS_ROOT", kScratch, 1);
            chdir(kScratch);
            args.insert(args.end(), { "--tools", kTools });
        }
        for (const auto & a : args) {
            std::printf("ps5lm-app: arg %s\n", a.c_str());
        }
        g_server_args = args;
        g_server_rc = -1;
        running = path;
        stats.set_model(model_part);
        stats.set_state(ServerState::loading);
        publish(stats);
        pthread_attr_t attr;
        pthread_attr_init(&attr);
        pthread_attr_setstacksize(&attr, 16u << 20);  // the console's default stack is small
        pthread_create(&server, &attr, run_server, nullptr);
        server_started = true;
        notify("PS5MM：正在把模型加载到 GPU");
    }

    void stop() {
        if (!server_started) {
            return;
        }
        llama_server_terminate();
        // With a reply in flight llama-server can stay inside its HTTP thread
        // pool forever (unload during generation hung the app). We are about
        // to be replaced by LoadExec anyway, so wait 10 s at most.
        for (int i = 0; i < 100 && g_server_rc < 0; ++i) {
            usleep(100 * 1000);
        }
        if (g_server_rc >= 0) {
            pthread_join(server, nullptr);
        } else {
            std::printf("ps5lm-app: llama_server did not return in 10 s; restarting anyway\n");
        }
        server_started = false;
        running.clear();
        log_memory("after unloading");
    }
};

// A thread with a 16 MiB stack, as llama-server's: the console's default is small.
pthread_t start_thread(std::function<void()> & fn) {
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setstacksize(&attr, 16u << 20);
    pthread_t t{};
    pthread_create(&t, &attr, [](void * p) -> void * {
        (*static_cast<std::function<void()> *>(p))();
        return nullptr;
    }, &fn);
    return t;
}

bool load_font(hui::gfx::Renderer & renderer, const char * name, hui::gfx::Font * font, hui::ui::FontRef * ref) {
    std::string data;
    const std::string path = std::string(kAssets) + "/fonts/" + name;
    // 32 MiB, not save::read_file's 4 MiB default: the regular face carries the
    // CJK glyphs the chat draws (GB2312, 6763 ideographs), so it is ~17 MiB and
    // the default refuses it — which silently killed the whole dashboard.
    if (!hui::save::read_file(path, &data, 32u << 20) || !font->load(data)) {
        std::printf("ps5lm-app: font %s failed\n", name);
        return false;
    }
    ref->font = font;
    ref->texture = renderer.batch().create_font_texture(*font);
    return true;
}

}  // namespace


int main(int argc, char ** argv) {

    // /data first: the log, the settings and the models live there.
    const std::string data = open_data();
    // stdout and stderr to a file the PC can fetch over FTP.
    if (std::freopen(kLog, "w", stdout) != nullptr) {
        setvbuf(stdout, nullptr, _IOLBF, 0);
    }
    if (std::freopen(kLog, "a", stderr) != nullptr) {
        // 块缓冲，不是无缓冲：加载 Qwen3-TTS 时 llama.cpp 给两千多个 codec token
        // 各打一行，无缓冲等于每行一次 write()，实测 0.72 秒一行、全程 25 分钟才
        // 轮到加载 tensor。攒成 64 KiB 再写，两三千行也就三四次系统调用。
        // 崩溃也不瞎：关键行都在 stdout，那边 _IOLBF，随时落盘。
        static char s_err_buf[64 * 1024];
        setvbuf(stderr, s_err_buf, _IOFBF, sizeof s_err_buf);
    }
    std::printf("ps5lm-app: version " PS5LM_VERSION "\n");
    // audio.cpp 引擎已移除（2026-11-05）：8004 那个槽位改给视频。
    std::printf("ps5lm-app: /data %s\n", data.c_str());
    if (data.rfind("closed", 0) == 0) {
        notify("PS5MM 写不了 /data。OnionHEN 下把 PPSA99577 加进 app_jailbreak.exact_title_ids "
               "in /data/OnionHEN/config.ini and start PS5MM again.");
    }
    // One device-local heap over the whole pool (RADV splits an APU's 2/3 to
    // 1/3), and a HOME for llama.cpp, which throws without one.
    setenv("radv_enable_unified_heap_on_apu", "true", 1);
    setenv("HOME", "/data/PS5MM", 0);
    setenv("LLAMA_CACHE", "/data/PS5MM/cache", 0);
    // Driver and backend switches to measure with, one NAME=value a line in
    // env.txt, set before the GPU opens; only the driver's, ggml's and llama's.
    for (const auto & line : read_lines(kEnv)) {
        const size_t eq = line.find('=');
        const std::string name = line.substr(0, eq == std::string::npos ? 0 : eq);
        bool known = false;
        for (const char * prefix : { "RADV_", "MESA_", "ACO_", "GGML_", "LLAMA_" }) {
            known = known || name.rfind(prefix, 0) == 0;
        }
        if (known) {
            setenv(name.c_str(), line.c_str() + eq + 1, 1);
        }
        std::printf("ps5lm-app: env %s%s\n", line.c_str(), known ? "" : " (ignored)");
    }
    mkdir(kModels, 0777);
    std::printf("ps5lm-app: start\n");
    // 越早越好：必须在任何引擎、任何模型加载之前就在听。
    exit_listener_start();

    // The screen first: it takes from the same memory as the model.
    Display display;
    if (!display.open(1920, 1080)) {
        std::printf("ps5lm-app: no display\n");
    }
    hui::gfx::Renderer renderer;
    hui::gfx::Font regular, semibold, headline, mono;
    hui::ui::Fonts fonts;
    const bool ui_ok = renderer.init() && load_font(renderer, "manrope-500.huifont", &regular, &fonts.regular) &&
                       load_font(renderer, "manrope-600.huifont", &semibold, &fonts.semibold) &&
                       load_font(renderer, "manrope-200.huifont", &headline, &fonts.display) &&
                       load_font(renderer, "dejavu-sans-mono.huifont", &mono, &fonts.mono);
    fonts.pixel = fonts.mono;
    fonts.hand = fonts.regular;
    std::printf("ps5lm-app: dashboard %s\n", ui_ok ? "ready" : "failed");

    Dashboard dash(fonts);
    DashboardFrame frame;
    const auto render = [&] {
        // 退出流程已经把电视还回去了（display_shutdown）：这一帧什么都不画。
        // 主循环比 /quit 那条线程活得久，不挡住的话它会拿着已销毁的上下文调 GL。
        if (display_released()) {
            return;
        }
        frame.backdrop = {};
        frame.scene.clear();
        frame.overlay.clear();
        frame.glass = false;
        frame.glass_texture = renderer.glass_texture();
        dash.draw(frame);
        renderer.begin();
        renderer.backdrop(frame.backdrop);
        renderer.draw(frame.scene);
        if (frame.glass) {
            renderer.glass();
        }
        renderer.draw(frame.overlay);
        display.present(renderer);
    };
    // The splash at once, so a restart for a model is never a black screen.
    if (ui_ok) {
        dash.set_busy("Starting", "正在打开 GPU 并读取模型");
        render();
        display.swap();
    }
    sceSystemServiceHideSplashScreen();

    StatsCollector stats;
    set_activity_sink(&stats);  // llama-server's request hooks (patches/0007) report here
    Models models;
    models.settings = load_settings(kSettings);
    // 读完设置才知道文字引擎占哪个槽位，端口得这时候才定得下来
    stats.start(ps5mm::port_of_slot(models.settings.text_slot));
    ps5mm::print_caps();
    // The model about to load, by name, for Home while the GPU opens.
    {
        std::vector<std::string> next = read_lines(kArgs);
        const auto m = std::find(next.begin(), next.end(), "-m");
        next = m != next.end() && m + 1 != next.end() ? std::vector<std::string>{ *(m + 1) } : read_lines(kChoice);
        if (next.empty() && models.settings.auto_load) {
            next = { models.settings.default_model };
        }
        if (!next.empty() && !next[0].empty() && next[0] != "none") {
            Live pending;
            pending.model_label = base_name(next[0]);
            stats.set_model(pending);
            stats.set_state(ServerState::loading);
        }
        stats.set_phase("正在打开 GPU 并读取模型");
    }

    // The slow part on a thread of its own (the GPU opening, every model's
    // header, the model's start) while the screen keeps moving: the splash
    // for a moment, then Home, where the load shows.
    std::function<void()> boot = [&] {
        for (size_t i = 0; i < ggml_backend_dev_count(); i++) {
            ggml_backend_dev_t dev = ggml_backend_dev_get(i);
            size_t free = 0, total = 0;
            ggml_backend_dev_memory(dev, &free, &total);
            std::printf("ps5lm-app: device %zu %s (%s): %.2f / %.2f GiB free\n", i, ggml_backend_dev_name(dev),
                        ggml_backend_dev_description(dev), free / 1073741824.0, total / 1073741824.0);
            // The PS5 is an APU: ggml calls its GPU integrated.
            const auto type = ggml_backend_dev_type(dev);
            if (type == GGML_BACKEND_DEVICE_TYPE_GPU || type == GGML_BACKEND_DEVICE_TYPE_IGPU) {
                models.budget_gib = free / 1073741824.0;
            }
        }

        models.scan(stats);

        // Which model: app-args.txt verbatim, else model.txt, which the library
        // writes just before restarting the app for a switch and which is used
        // once, else the default model when Settings asks for it at launch. A
        // plain launch otherwise loads nothing and opens the library.
        Live model_part;
        std::vector<std::string> args = read_lines(kArgs);
        std::string path;
        if (!args.empty()) {
            const auto m = std::find(args.begin(), args.end(), "-m");
            path = m != args.end() && m + 1 != args.end() ? *(m + 1) : "";
            model_part.model_label = base_name(path);
            const ModelInfo info = read_model_info(path);
            model_part.model_arch = info.arch;
            model_part.model_gib = info.file_bytes / 1073741824.0;
            model_part.model_file = path;
            model_part.args = args;
            // app-args.txt bypasses the planner, so nothing else fills these in
            // and the dashboard drew "0k" for the context. Read the ones the
            // file actually sets.
            const auto arg_after = [&](const char * flag) -> const std::string * {
                const auto it = std::find(args.begin(), args.end(), flag);
                return it != args.end() && it + 1 != args.end() ? &*(it + 1) : nullptr;
            };
            if (const std::string * c = arg_after("-c")) {
                model_part.ctx = (uint32_t) std::strtoul(c->c_str(), nullptr, 10);
            }
            if (const std::string * k = arg_after("-ctk")) {
                model_part.kv_type = *k;
            }
            std::printf("ps5lm-app: app-args.txt overrides the planner\n");
        } else {
            auto chosen = read_lines(kChoice);
            unlink(kChoice);
            if (chosen.empty() && models.settings.auto_load && !models.settings.default_model.empty()) {
                chosen = { models.settings.default_model };  // "none" after an unload keeps it from coming back
            }
            for (const auto & r : models.rows) {
                if (r.fits && !chosen.empty() && r.file == chosen[0]) {
                    path = r.file;
                }
            }
            if (!path.empty()) {
                args = models.args_for(path, model_part);
            }
        }
        // A projector this llama.cpp cannot read stops the server (#15); the
        // restart after it loads the same model text only, this once.
        if (access(kTextOnly, F_OK) == 0) {
            unlink(kTextOnly);
            const auto mm = std::find(args.begin(), args.end(), "--mmproj");
            if (mm != args.end()) {
                std::printf("ps5lm-app: loading without %s\n", mm + 1 != args.end() ? (mm + 1)->c_str() : "the projector");
                args.erase(mm, std::min(mm + 2, args.end()));
                model_part.args = args;
            }
        }
        log_memory("before loading");
        if (!args.empty()) {
            // The introspection API is off unless the setting asks for it. The
            // server reads LLAMA_INTROSPECT when its thread starts, below. The
            // setting wins over env.txt, so the row always says what the server does.
            setenv("LLAMA_INTROSPECT", models.settings.introspect ? "1" : "0", 1);
            models.start(path, args, stats, model_part);
        } else {
            stats.set_state(ServerState::no_model);
            if (models.rows.empty()) {
                notify("PS5MM：没有模型。把 .gguf 复制到 /data/PS5MM/models，或 U 盘上的 PS5LM/models");
            }
        }
        stats.set_phase("");

    };
    std::atomic<bool> booted{ false };
    std::function<void()> boot_then = [&] {
        boot();
        booted = true;
    };
    const pthread_t booting = start_thread(boot_then);
    {
        hui::ui::Feedback quiet;  // no sounds yet: the mixer starts after
        const int64_t start = hui::sys::monotonic_us();
        int64_t at = start;
        while (ui_ok && !booted) {
            const int64_t now = hui::sys::monotonic_us();
            if (now - start > 1200000) {
                dash.set_busy("");
            }
            dash.set_live(stats.snapshot());
            quiet.clear();
            dash.update(hui::InputFrame{}, std::min(0.05f, (float) (now - at) / 1e6f), quiet);
            at = now;
            render();
            display.swap();
        }
    }
    pthread_join(booting, nullptr);

    // The engines on a thread of their own: loading a 1.4 GB speech model and a
    // 10 GB video model takes minutes, and the main loop below must be reading
    // the pad from the first frame. PS5LM's boot ends before its server starts
    // for the same reason.
    // The models come from settings.json, so the Settings page on the TV is what
    // decides them — no path is baked in beyond the defaults. Each engine takes
    // the next port in turn: 8001, 8002, up to 8005.
    // 两个引擎各开一个线程，不串行：语音那个加载慢（Qwen3-TTS 的 tokenizer 要注册
    // 两千多个 codec token），早先串行时它一卡，后面的画图引擎永远轮不到。
    // 端口写死（8003 语音 / 8002 画图），谁先起都不变。
    {
        // 启动加载清单：勾了哪些模型，启动那一刻就派给对应引擎。
        // 清单空 = 照老规矩来（auto_load / tts_backbone / sd_diffusion）。
        const Settings boot = models.settings;
        const bool use_list = !boot.boot_models.empty();
        const auto pick_boot = [&boot, use_list](std::initializer_list<const char *> kinds) -> std::string {
            if (!use_list) {
                return std::string();
            }
            for (const auto & path : boot.boot_models) {
                const std::string k = ps5lm::model_kind(path);
                for (const char * want : kinds) {
                    if (k == want) {
                        return path;
                    }
                }
            }
            return std::string();
        };
        const std::string boot_speech  = pick_boot({ "speech" });
        const std::string boot_picture = pick_boot({ "picture", "video" });
        // 文字那条走既有那条路：把清单里的文字模型写回 settings，后面按 auto_load 起
        if (use_list) {
            const std::string boot_text = pick_boot({ "text", "decision" });
            models.settings.auto_load = !boot_text.empty();
            if (!boot_text.empty()) {
                models.settings.default_model = boot_text;
            }
        }
        // 语音引擎：清单勾了就用清单那个（codec 从同目录找），否则用设置里那对
        const std::string tts_model = use_list ? boot_speech : boot.tts_backbone;
        const std::string tts_codec = use_list ? (boot_speech.empty() ? std::string() : ps5lm::find_mmproj(boot_speech))
                                               : boot.tts_mmproj;
        const std::string voices_dir = boot.voices_dir;
        const int         tts_slot   = boot.speech_slot;
        // 语音引擎二选一：
        //   tts_backbone 指向 VoxCPM 的单文件 GGUF（名字里带 voxcpm）→ VoxCPM.cpp（Vulkan）
        //   否则走原来的 llama.cpp Qwen3-TTS（CPU，需要 mmproj）
        // VoxCPM 无状态、单文件、跑 Vulkan；老引擎连发会退化，且 GPU 上会锁死进程。
        const bool use_voxcpm = tts_model.find("voxcpm") != std::string::npos;
        g_speech_voxcpm = use_voxcpm;
        std::thread([tts_model, tts_codec, voices_dir, tts_slot, use_voxcpm] {
            if (tts_model.empty() || access(tts_model.c_str(), F_OK) != 0) {
                std::printf("ps5mm-app: no speech model (see Settings)\n");
                std::fflush(nullptr);
                if (!tts_model.empty() && !use_voxcpm) {
                    tts_server_abandon();
                }
                return;
            }
            const int speech_port = ps5mm::port_of_slot(tts_slot);
            if (use_voxcpm) {
                std::printf("ps5mm-app: speech engine (VoxCPM, Vulkan) on :%d (%s)\n", speech_port,
                            tts_model.c_str());
                std::fflush(nullptr);
                if (voxcpm_server_start(tts_model.c_str(), voices_dir.c_str(), speech_port) == 0) {
                    notify(("PS5MM: speech ready on :" + std::to_string(speech_port)).c_str());
                } else {
                    notify("PS5MM: the speech model did not load; text still works");
                }
                return;
            }
            if (tts_codec.empty() || access(tts_codec.c_str(), F_OK) != 0) {
                std::printf("ps5mm-app: no speech codec (see Settings)\n");
                std::fflush(nullptr);
                tts_server_abandon();
                return;
            }
            std::printf("ps5mm-app: speech engine (llama.cpp, CPU) on :%d (%s)\n", speech_port,
                        tts_model.c_str());
            std::fflush(nullptr);
            if (tts_server_start(tts_model.c_str(), tts_codec.c_str(), voices_dir.c_str(), speech_port) == 0) {
                notify(("PS5MM: speech ready on :" + std::to_string(speech_port)).c_str());
            } else {
                notify("PS5MM: the speech model did not load; text still works");
            }
        }).detach();

        // audio.cpp 引擎已移除（2026-11-05）：
        //   5 次真机尝试全部失败，它的 model_load 一进去就不返回，还会把整个
        //   payload 链拖死（只能物理关机）。它的 gguf 是自家格式，和 llama/sd
        //   的约定不兼容。8004 这个槽位改给视频用。
        //   代码和 .deps/audio-acx 都留着，需要时能随时接回来。

        // 视频入口：和图片共用同一个 sd 上下文（12 GiB 装不下两套权重），
        // 但挂在独立端口上，前端能分开调。忙的时候 503，不会把请求排死。
        {
            const int video_port = ps5mm::port_of_slot(boot.video_slot);
            std::printf("ps5mm-app: video route on :%d\n", video_port);
            std::fflush(nullptr);
            sd_server_start_video(video_port);
        }

        // 3D 引擎：TRELLIS.2 图生 3D（TRX_ 前缀），占 video 之后的下一个空闲槽位。
        // 模型约定在 /data/PS5MM/trellis/（trellis.gguf / naf.gguf / birefnet.gguf）。
        {
            // 3D 取第一个没被前面四个引擎占用的槽位。
            // （原来写的是「第二个空闲」，那是给 audio 留位的年代；audio 删掉之后
            //   只剩一个空位，那个算法永远取不到值，3D 压根没启动。）
            int slot3d = 0;
            for (int s = 1; s <= 5; ++s) {
                if (s == boot.text_slot || s == boot.picture_slot || s == boot.speech_slot ||
                    s == boot.video_slot) {
                    continue;
                }
                slot3d = s;
                break;
            }
            if (slot3d != 0) {
                const int p3d = ps5mm::port_of_slot(slot3d);
                std::thread([p3d, t_dir = boot.trellis_dir] {
                    TrellisPaths paths{ t_dir.c_str(), kOutputs, "Vulkan" };
                    std::printf("ps5mm-app: 3D engine starting on :%d (runs on request)\n", p3d);
                    std::fflush(nullptr);
                    if (trellis_server_start(paths, p3d) != 0) {
                        notify("PS5MM: the 3D engine did not start");
                        return;
                    }
                    notify(("PS5MM: image to 3D on :" + std::to_string(p3d)).c_str());
                }).detach();
            }
        }

        // 画图引擎：路由总是起（/health 要能查），勾了模型就在启动时把它加载进去
        const std::string sd_model  = use_list ? boot_picture : boot.sd_diffusion;
        const std::string sd_video  = boot.sd_video;
        const std::string sd_clip_l = boot.sd_clip_l, sd_clip_g = boot.sd_clip_g;
        const std::string sd_t5xxl  = boot.sd_t5xxl,  sd_vae    = boot.sd_vae;
        // 视频那一套的编码器：留空 = 沿用上面那对（老配置）。
        const std::string sd_video_t5xxl = boot.sd_video_t5xxl.empty() ? boot.sd_t5xxl : boot.sd_video_t5xxl;
        const std::string sd_video_vae   = boot.sd_video_vae.empty() ? boot.sd_vae : boot.sd_video_vae;
        const std::string sd_esrgan = boot.sd_esrgan;
        // 只有启动清单里勾了画图模型才预加载；清单空 = 只起路由，等第一次请求。
        const bool preload_picture  = use_list && !boot_picture.empty();
        const int  sd_slot          = boot.picture_slot;
        std::thread([sd_model, sd_video, sd_clip_l, sd_clip_g, sd_t5xxl, sd_vae, sd_esrgan, sd_video_t5xxl,
                     sd_video_vae, preload_picture, sd_slot] {
            SdModels sd_models{ sd_model.empty() ? nullptr : sd_model.c_str(),
                                sd_clip_l.empty() ? nullptr : sd_clip_l.c_str(),
                                sd_clip_g.empty() ? nullptr : sd_clip_g.c_str(),
                                sd_t5xxl.empty() ? nullptr : sd_t5xxl.c_str(),
                                sd_vae.empty() ? nullptr : sd_vae.c_str(),
                                sd_esrgan.empty() ? nullptr : sd_esrgan.c_str(), kOutputs,
                                sd_video.empty() ? nullptr : sd_video.c_str(),
                                sd_video_t5xxl.empty() ? nullptr : sd_video_t5xxl.c_str(),
                                sd_video_vae.empty() ? nullptr : sd_video_vae.c_str() };
            // 视频模型交给 sd_server：它按请求决定装哪一套（见 ensure_ctx）
            const int p = ps5mm::port_of_slot(sd_slot);
            std::printf("ps5mm-app: picture engine starting on :%d (%s)\n", p,
                        preload_picture ? "preloading" : "loads on first request");
            std::fflush(nullptr);
            if (sd_server_start(sd_models, p) != 0) {
                notify("PS5MM: the picture engine did not start");
                return;
            }
            if (preload_picture) {
                if (sd_server_preload() != 0) {
                    notify("PS5MM：图像模型没加载上，第一次请求时会再试");
                }
            } else {
                notify(("PS5MM: pictures and video on :" + std::to_string(p)).c_str());
            }
        }).detach();
    }

    // Input and sound, as ps5-homebrew-ui's own app does.
    hui::ps5::Pad pad;
    pad.open();
    hui::InputTracker tracker;
    hui::audio::Mixer mixer;
    hui::ps5::AudioOut audio_out;
    audio_out.start(mixer);
    hui::audio::SoundBank sounds;
    sounds.load(std::string(kAssets) + "/audio/sfx");

    dash.set_busy("");
    Market    market;
    market.start(models.budget_gib);
    int  saved_seen = 0;  // downloads finished, as last seen
    dash.set_settings(models.settings);
    bool      scratch_warned = false;
    // Downloads left queued or running carry on, on their own page.
    unlink("/data/PS5MM/download.txt");  // the queue file replaced this one (v0.7.0)
    market.load_queue();
    for (const auto & d : market.snapshot().downloads) {
        // Running already, maybe: the queue's thread starts it at once.
        if (d.state == DownloadState::queued || d.state == DownloadState::running) {
            dash.show_downloads();
            break;
        }
    }
    hui::ui::Feedback feedback;
    hui::PadSample samples[64];
    int64_t last = hui::sys::monotonic_us();
    bool was_serving = false;
    bool rescanning = false;
    uint64_t restart_at = 0;  // the frame to stop the model and restart on, or 0
    // 首页监控板：五个槽位的卡片，每 0.5 秒一次。槽位是「配置 + 调度」视图，
    // 不是五个模型同时驻留的承诺 —— 池子只有 12 GB 上下，谁来谁走由人看着办。
    // 内存口径 = 模型文件字节数（权重）；文字的 KV 由 llama.cpp 自报，另外算。
    const auto collect_engines = [&models](const Live & snap) -> std::vector<EngineCard> {
        std::vector<EngineCard> cards;
        const Settings & st = models.settings;
        const auto file_gib = [](const std::string & p) -> double {
            if (p.empty()) {
                return 0.0;
            }
            struct stat sb = {};
            return stat(p.c_str(), &sb) == 0 ? (double) sb.st_size / 1073741824.0 : 0.0;
        };
        const auto base_name_of = [](const std::string & p) -> std::string {
            const size_t at = p.find_last_of('/');
            return at == std::string::npos ? p : p.substr(at + 1);
        };

        // 槽位 1 · 8001 文字
        {
            EngineCard c;
            c.slot       = st.text_slot;
            c.port       = ps5mm::port_of_slot(st.text_slot);
            c.name       = "文字";
            c.kind       = "text";
            c.state      = snap.state == ServerState::ready        ? "就绪"
                         : snap.state == ServerState::generating   ? "生成中"
                         : snap.state == ServerState::loading      ? "加载中"
                         : snap.state == ServerState::failed       ? "出错"
                         : snap.state == ServerState::no_model     ? (st.default_model.empty() ? "未配置" : "未加载")
                                                                   : "未启动";
            c.model      = !snap.model_file.empty() ? snap.model_file : st.default_model;
            c.loaded     = snap.state == ServerState::ready || snap.state == ServerState::generating;
            c.model_gib  = snap.model_gib > 0 ? snap.model_gib : file_gib(st.default_model);
            c.extra_gib  = snap.kv_gib;
            c.tps        = snap.gen_tps;
            c.ctx        = snap.ctx;
            c.kv_type    = snap.kv_type;
            c.requests   = snap.requests;
            if (snap.state == ServerState::generating) {
                char t[64];
                std::snprintf(t, sizeof t, "%.1f token/s", snap.gen_tps);
                c.activity = t;
            } else if (snap.requests > 0) {
                c.activity = "已回答 " + std::to_string((unsigned long long) snap.requests) + " 次请求";
            }
            cards.push_back(std::move(c));
        }
        // 槽位 2 · 8002 图像 / 视频
        {
            EngineCard c;
            c.slot    = st.picture_slot;
            c.port    = ps5mm::port_of_slot(st.picture_slot);
            c.name    = "图像";
            c.kind    = "picture";
            int step = 0, steps = 0;
            sd_server_progress(&step, &steps);
            // 图片和视频共用一套 sd 上下文：要问一句这次跑的是谁，
            // 否则跑视频的时候图片卡也写着「生成中」。
            const bool busy_picture = step > 0 && steps > 0 && !sd_server_video_active();
            const bool live_route   = sd_server_listening();
            const bool loaded       = sd_server_ready();
            c.state   = st.sd_diffusion.empty() ? "未配置"
                      : !live_route            ? "未启动"
                      : busy_picture           ? "生成中"
                      : loaded                 ? "就绪"
                                               : "等第一次请求";
            c.model     = st.sd_diffusion;
            c.loaded    = loaded;   // 懒加载时 false：下面的数字是「预计」，不算已用
            c.model_gib = file_gib(st.sd_diffusion) + file_gib(st.sd_t5xxl) + file_gib(st.sd_vae) +
                          file_gib(st.sd_clip_l) + file_gib(st.sd_clip_g);
            c.step      = busy_picture ? step : 0;
            c.steps     = busy_picture ? steps : 0;
            c.width     = (int) st.sd_width;
            c.height    = (int) st.sd_height;
            c.frames    = 0;   // 帧数是视频的属性，别混进图片卡
            c.fps       = 0;
            c.cfg       = st.sd_cfg_x10 / 10.0;
            if (step > 0 && steps > 0) {
                c.activity = "第 " + std::to_string(step) + " / " + std::to_string(steps) + " 步";
            }
            if (!st.sd_video.empty()) {
                c.detail = "视频另用 " + base_name_of(st.sd_video);
            }
            cards.push_back(std::move(c));
        }
        // 槽位 3 · 8003 语音
        {
            EngineCard c;
            c.slot      = st.speech_slot;
            c.port      = ps5mm::port_of_slot(st.speech_slot);
            c.name      = "语音";
            c.kind      = "speech";
            const int tts = g_speech_voxcpm ? voxcpm_server_status() : tts_server_status();
            c.state     = st.tts_backbone.empty() ? "未配置"
                        : tts == 2                ? ((g_speech_voxcpm ? voxcpm_server_busy() : tts_server_busy()) ? "生成中" : "就绪")
                        : tts == 1                ? "加载中"
                        : tts == -1               ? "出错"
                                                  : "未启动";
            c.model     = st.tts_backbone;
            c.loaded    = tts == 2;
            c.model_gib = file_gib(st.tts_backbone) + file_gib(st.tts_mmproj);
            c.lang      = st.tts_lang;
            c.voice     = base_name_of(st.voices_dir);
            c.requests  = (uint64_t) (g_speech_voxcpm ? voxcpm_server_requests() : tts_server_requests());
            if (c.requests > 0) {
                c.activity = "已合成 " + std::to_string((unsigned long long) c.requests) + " 段语音";
            }
            cards.push_back(std::move(c));
        }
        // 视频引擎卡：和图片共用 sd 上下文，但端口独立。
        {
            EngineCard c;
            c.slot     = st.video_slot;
            c.port     = ps5mm::port_of_slot(st.video_slot);
            c.name     = "视频";
            c.kind     = "video";
            int vstep = 0, vsteps = 0;
            sd_server_progress(&vstep, &vsteps);
            const bool busy_video = vstep > 0 && vsteps > 0 && sd_server_video_active();
            const bool sd_loaded  = sd_server_ready();
            c.state    = st.sd_video.empty() ? "未配置"
                       : !sd_server_listening() ? "未启动"
                       : busy_video           ? "生成中"
                       : sd_loaded && sd_server_video_active() ? "就绪"
                                              : "等请求";
            c.model    = st.sd_video;
            c.loaded   = sd_loaded && sd_server_video_active();
            c.model_gib = file_gib(st.sd_video) + file_gib(st.sd_video_t5xxl) + file_gib(st.sd_video_vae);
            c.step     = busy_video ? vstep : 0;
            c.steps    = busy_video ? vsteps : 0;
            c.width    = (int) st.sd_width;
            c.height   = (int) st.sd_height;
            c.frames   = (int) st.sd_frames;
            c.fps      = (int) st.sd_fps;
            c.detail   = busy_video ? ("第 " + std::to_string(vstep) + " / " + std::to_string(vsteps) + " 步")
                                    : "和图片共用一套 sd 上下文（12 GiB 装不下两套）";
            cards.push_back(std::move(c));
        }
        // 3D 引擎卡
        {
            int slot3d = 0;
            for (int s = 1; s <= 5; ++s) {
                if (s == st.text_slot || s == st.picture_slot || s == st.speech_slot ||
                    s == st.video_slot) {
                    continue;
                }
                slot3d = s;
                break;
            }
            if (slot3d != 0) {
                EngineCard c;
                c.slot   = slot3d;
                c.port   = ps5mm::port_of_slot(slot3d);
                c.name   = "三维";
                c.kind   = "trellis";
                c.state  = trellis_server_listening() ? "等请求" : "未启动";
                c.detail = "TRELLIS.2 图生 3D";
                if (trellis_server_last_ms() > 0) {
                    c.activity = std::to_string(trellis_server_last_ms()) + " ms";
                }
                cards.push_back(std::move(c));
            }
        }
        // 其余槽位预留：路由、引擎都还不存在，界面只留位置。
        // 三个真引擎占了哪几个槽位，这里就跳过哪几个 —— 否则会出现两张卡抢同一个端口。
        for (int s = 1; s <= 5; ++s) {
            if (s == st.text_slot || s == st.picture_slot || s == st.speech_slot) {
                continue;
            }
            // 3D 引擎占 audio 之后的下一个空闲槽位，也跳开。
            {
                int taken = 0, slot3d = 0;
                for (int q = 1; q <= 5; ++q) {
                    if (q == st.text_slot || q == st.picture_slot || q == st.speech_slot) {
                        continue;
                    }
                    if (taken == 1) {
                        slot3d = q;
                        break;
                    }
                    taken++;
                }
                if (s == slot3d) {
                    continue;
                }
            }
            // 视频槽位也是真引擎，跳开它。
            if (s == st.video_slot) {
                continue;
            }
            EngineCard c;
            c.slot     = s;
            c.port     = 8000 + s;
            c.name     = "预留";
            c.kind     = "reserved";
            c.state    = "预留";
            c.reserved = true;
            c.detail   = "留给以后的引擎";
            cards.push_back(std::move(c));
        }
        // 三张真卡 + 若干预留卡，按槽位号排好，界面第 i 格永远是 i+1 号槽。
        std::sort(cards.begin(), cards.end(), [](const EngineCard & a, const EngineCard & b) {
            return a.slot < b.slot;
        });
        return cards;
    };

    uint64_t menu_arm = 0;   // 上一次按 Options 的帧号：3 秒内再按一下就退出

    for (uint64_t n = 0;; ++n) {
        const int64_t now = hui::sys::monotonic_us();
        const float dt = n == 0 ? 1.0f / 60.0f : std::min(0.05f, (float) (now - last) / 1e6f);
        last = now;

        const size_t count = pad.read(samples);
        const hui::InputFrame input = tracker.update(std::span<const hui::PadSample>(samples, count), (uint64_t) now);
        // Options 连按两下退出到主屏：PS 键在 native title 下常被显示 plane 挡住，
        // 手柄得有一条自己的退路。走和 quit 文件同一条正路。
        if (input.is_pressed(hui::Action::menu)) {
            if (menu_arm != 0 && n - menu_arm < 180) {
                std::printf("ps5mm-app: exit to home (Options pressed twice)\n");
                tts_server_terminate();
                sd_server_terminate();
                std::fflush(nullptr);
                exit_to_home();
            }
            menu_arm = n == 0 ? 1 : n;
            notify("再按一次 Options 退出到主屏");
        }
        Live live = stats.snapshot();
        if (g_server_rc >= 0 && live.state != ServerState::failed && live.state != ServerState::no_model) {
            stats.set_state(ServerState::failed);
            const bool projector = std::find(g_server_args.begin(), g_server_args.end(), "--mmproj") != g_server_args.end();
            if (live.state == ServerState::loading && projector && restart_at == 0) {
                std::ofstream(kChoice) << models.running << "\n";
                std::ofstream(kTextOnly) << models.running << "\n";
                notify("PS5MM：图像投影器没加载，只加载文本部分");
                dash.set_busy("Loading " + base_name(models.running) + " text only",
                              "它的图像投影器没加载，详见 /data/PS5MM/llama.log");
                restart_at = n + 3;
            } else {
                notify("PS5MM：服务已停止，详见 /data/PS5MM/llama.log");
            }
        }
        const bool serving = live.state == ServerState::ready || live.state == ServerState::generating;
        if (serving && !was_serving) {
            notify(live.decision.empty() ? "PS5MM 就绪，局域网内用浏览器聊天" : "PS5MM 就绪，决策接口 /v1/systemone");
        }
        was_serving = serving;
        if (n % 30 == 0) {
            models.publish(stats);
            // 存进 stats，不要只写当帧的 live —— 否则其余 29 帧的 engines 是空的，
            // 界面就会每 0.5 秒在「三张卡」和「还没有引擎」之间闪一次。
            stats.set_engines(collect_engines(live));
            live = stats.snapshot();
        }
        dash.set_live(live);
        feedback.clear();
        // A button pressed from the PC (scripts/ps5lm-app.sh press r1), for
        // testing the screens without a controller in hand.
        hui::InputFrame in = input;
        if (n % 20 == 10) {
            const std::string key = take_request_file("/data/PS5MM/press");
            const struct {
                const char *   name;
                hui::Action    action;
                hui::Direction nav;
            } keys[] = {
                { "up", hui::Action::up, hui::Direction::up },
                { "down", hui::Action::down, hui::Direction::down },
                { "left", hui::Action::left, hui::Direction::left },
                { "right", hui::Action::right, hui::Direction::right },
                { "cross", hui::Action::confirm, hui::Direction::none },
                { "circle", hui::Action::back, hui::Direction::none },
                { "triangle", hui::Action::north, hui::Direction::none },
                { "square", hui::Action::west, hui::Direction::none },
                { "l1", hui::Action::page_prev, hui::Direction::none },
                { "r1", hui::Action::page_next, hui::Direction::none },
                { "l2", hui::Action::jump_prev, hui::Direction::none },
                { "r2", hui::Action::jump_next, hui::Direction::none },
            };
            for (const auto & k : keys) {
                if (key == k.name) {
                    in.connected = true;
                    in.pressed |= hui::action_bit(k.action);
                    in.nav = k.nav;
                }
            }
        }
        dash.update(in, dt, feedback);
        for (const auto & cue : feedback.cues) {
            if (!models.settings.sounds) {
                break;
            }
            sounds.play(mixer, cue.set == hui::audio::SoundSet::count ? hui::audio::SoundSet::glass : cue.set, cue);
        }
        if (feedback.rumble_strength > 0.0f) {
            pad.rumble(feedback.rumble_strength, feedback.rumble_seconds);
        }
        pad.tick(dt);

        // The scratch folder: its size for the dashboard, and one warning each
        // time it grows past the limit.
        if (n % 600 == 300) {
            const double gib = folder_bytes(kScratch) / 1073741824.0;
            stats.set_scratch(gib);
            const bool over = gib > models.settings.scratch_limit_gib;
            if (over && !scratch_warned) {
                char text[128];
                std::snprintf(text, sizeof(text), "PS5MM：聊天 scratch 目录已占 %.1f GiB，在「设置」里清空", gib);
                notify(text);
                std::printf("ps5lm-app: %s\n", text + 7);
            }
            scratch_warned = over;
        }
        if (n % 10 == 0) {
            MarketView mv = market.snapshot();
            // A finished download joins the library.
            if (mv.saved != saved_seen) {
                saved_seen = mv.saved;
                models.rescan(stats, false);
                notify(("PS5MM: " + mv.note).c_str());
            }
            dash.set_market(std::move(mv));
        }
        if (dash.wants_logs() && n % 60 == 0) {
            dash.set_logs(tail_lines(kLog), tail_lines(kLlamaLog));
        }

        // A settings rescan in the background: say so until it lands.
        if (models.poll_rescan(stats) && models.scan_shown) {
            char text[96];
            std::snprintf(text, sizeof(text), "按 %uk 上下文和 %s 缓存重新规划所有模型",
                          models.settings.ctx_cap / 1024, models.settings.kv_type.c_str());
            dash.set_busy("正在应用新的限制", text);
            rescanning = true;
        } else if (rescanning) {
            rescanning = false;
            dash.set_busy("");
        }
        // A restart asked for a few frames ago, once the busy screen is up.
        if (restart_at != 0 && n >= restart_at) {
            std::fflush(nullptr);
            models.stop();
            sceSystemServiceLoadExec("/app0/eboot.bin", nullptr);
        }

        Dashboard::Request req = dash.take_request();
        if (req.kind == Dashboard::Request::settings) {
            // The planner's limits change every row's plan; the loaded model
            // keeps its settings until it is loaded again.
            // Only the context and cache limits change the plans; rescanning
            // reads every model's header, seconds with a USB drive.
            const Settings was = models.settings;
            models.settings = dash.settings();
            save_settings(kSettings, models.settings);
            if (was.ctx_cap != models.settings.ctx_cap || was.kv_type != models.settings.kv_type) {
                models.rescan(stats);
            }
            std::printf("ps5lm-app: settings saved\n");
            // The server reads LLAMA_INTROSPECT only when it starts: restart with the
            // same model, so that the switch never says something the server does not do.
            if (was.introspect != models.settings.introspect && !models.running.empty() && restart_at == 0) {
                std::ofstream(kChoice) << models.running << "\n";
                std::printf("ps5lm-app: restarting %s with the introspection API %s\n", models.running.c_str(),
                            models.settings.introspect ? "on" : "off");
                dash.set_busy(std::string(models.settings.introspect ? "Opening" : "Closing") + " the logits and activations API",
                              "The app restarts with " + base_name(models.running));
                restart_at = n + 3;
            }
        }
        switch (req.kind) {
            case Dashboard::Request::ask:
                ask_self(ps5mm::port_of_slot(models.settings.text_slot), req.path, !live.decision.empty());
                break;
            case Dashboard::Request::market_search: market.search(req.path); break;
            case Dashboard::Request::market_open: market.open_repo(req.repo); break;
            case Dashboard::Request::market_plan: market.plan_file(req.repo, req.file); break;
            case Dashboard::Request::market_download: {
                MarketJob job;
                if (market.job(req.repo, req.file, req.path.empty() ? models.settings.download_dir : req.path, &job)) {
                    market.enqueue(job, free_gib(job.dir));
                }
                break;
            }
            case Dashboard::Request::suggested_download: {
                const Suggestion & s = kSuggestions[std::clamp(req.repo, 0, kSuggestionCount - 1)];
                const std::string dir = req.path.empty() ? models.settings.download_dir : req.path;
                for (const SuggestedFile * f : { &s.model, &s.mmproj }) {
                    if (f->file) {
                        market.enqueue({ s.repo, f->file, f->sha256, dir, f->bytes, f->save_as ? f->save_as : "" }, free_gib(dir));
                    }
                }
                dash.show_downloads();
                break;
            }
            case Dashboard::Request::download_pause: market.pause(req.repo); break;
            case Dashboard::Request::sd_preload:
                // 图像槽位的「加载」：预加载把整个模型拉进显存，几分钟，不能在主线程。
                std::thread([] {
                    if (sd_server_preload() != 0) {
                        notify("PS5MM：图像模型没加载上，第一次请求时会再试");
                    }
                }).detach();
                break;
            case Dashboard::Request::download_resume: market.resume(req.repo); break;
            case Dashboard::Request::download_remove: market.remove(req.repo); break;
            case Dashboard::Request::market_download_unload: {
                // Unload by restarting (as the library does); the queue,
                // saved to disk, starts the download in the new process.
                MarketJob job;
                if (market.job(req.repo, req.file, req.path.empty() ? models.settings.download_dir : req.path, &job) &&
                    market.enqueue(job, free_gib(job.dir))) {
                    std::ofstream(kChoice) << "none\n";
                    std::printf("ps5lm-app: restarting to download %s/%s without a model\n", job.repo.c_str(), job.file.c_str());
                    dash.set_busy("正在卸载 " + base_name(models.running), "app 将不带它重启，然后开始下载");
                    restart_at = n + 3;
                }
                break;
            }
            default: break;
        }
        if (req.kind == Dashboard::Request::clear_scratch) {
            std::error_code ec;
            for (const auto & e : std::filesystem::directory_iterator(kScratch, ec)) {
                std::filesystem::remove_all(e.path(), ec);
            }
            stats.set_scratch(folder_bytes(kScratch) / 1073741824.0);
            notify("PS5MM：scratch 目录已清空");
            std::printf("ps5lm-app: scratch folder cleared\n");
        }
        // The same requests from the PC (scripts/ps5lm-app.sh load|unload).
        if (n % 60 == 30 && req.kind == Dashboard::Request::none) {
            if (std::string p = take_request_file("/data/PS5MM/load"); !p.empty()) {
                req = { Dashboard::Request::load, p };
            } else if (!take_request_file("/data/PS5MM/unload").empty()) {
                req = { Dashboard::Request::unload, "" };
            } else if (std::string u = take_request_file("/data/PS5MM/fetch"); !u.empty()) {
                std::thread(probe_fetch, u).detach();
            } else if (!take_request_file("/data/PS5MM/bench-write").empty()) {
                std::thread(probe_write).detach();
            } else if (std::string q = take_request_file("/data/PS5MM/search"); !q.empty()) {
                market.search(q == "-" ? std::string() : q);  // a query typed on the PC
            }
        }
        if (req.kind == Dashboard::Request::unload || req.kind == Dashboard::Request::load) {
            // 正在卸载 in place leaves part of the model's GPU memory held
            // (about 5 GiB of a 6.8 GiB model, measured), so a model change
            // restarts the app: the system replaces the process (LoadExec on
            // our own eboot.bin, "Kill for LoadExec" in the log) and the new
            // one starts from the whole pool, with model.txt saying what to load.
            std::ofstream(kChoice) << (req.kind == Dashboard::Request::load ? req.path : std::string("none")) << "\n";
            if (req.kind == Dashboard::Request::load) {
                unlink(kArgs);  // the library's choice replaces a manual override
            }
            std::printf("ps5lm-app: restarting for %s\n", req.kind == Dashboard::Request::load ? req.path.c_str() : "no model");
            const bool loaded = !models.running.empty();
            if (req.kind == Dashboard::Request::load) {
                dash.set_busy(loaded ? "切换模型" : "Loading " + base_name(req.path),
                              loaded ? "正在卸载 " + base_name(models.running) + ", then the app restarts with " + base_name(req.path)
                                     : "app 将重启，把整块内存让给模型");
            } else {
                dash.set_busy("正在卸载 " + base_name(models.running), "app 将不加载模型重启，约 30 秒");
            }
            restart_at = n + 3;  // three frames with the busy screen on the TV first
        }

        if (ui_ok) {
            render();
            if (n % 60 == 45 && !take_request_file("/data/PS5MM/screenshot").empty()) {
                const bool ok = save_screen("/data/PS5MM/screen.bmp", display.width(), display.height());
                std::printf("ps5lm-app: screenshot %s\n", ok ? "saved" : "failed");
            }
        }
        display.swap();
        // 锁 60 帧：这一帧没花满 1/60 秒就把差的补睡回去。
        // PS5 的 CPU 很弱，界面不该占满它 —— 算力要留给推理。
        {
            const int64_t spent = hui::sys::monotonic_us() - now;
            const int64_t want  = 1000000 / 60;
            if (spent < want) {
                sceKernelUsleep((uint32_t) (want - spent));
            }
        }
        if (n % 60 == 0) {
            quit_if_asked();
        }
    }
}
