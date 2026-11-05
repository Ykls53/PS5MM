// What the dashboard shows, and the thread that measures it.
//
// llama-server reports its own work through /metrics and /slots, read here
// over loopback: tokens per second from the predicted-token counters, and
// how busy the GPU is from the seconds the server spent computing prompts
// and tokens (every layer runs on the GPU, so that time is GPU time). CPU
// use comes from getrusage, memory from the kernel's direct-memory pool and
// the platform heap.
//
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <cstdint>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

namespace ps5lm {

// A place models can live: internal storage, the M.2 slot, or a USB drive.
struct Drive {
    std::string name;    // "Internal storage", "M.2 drive", "USB drive"
    std::string models;  // where PS5LM keeps models on it
    double      free = 0, total = 0;  // GiB; total 0 when unknown (no ps5-exporter)
};

// A request another device made, and what was answered, for the Home page.
struct Exchange {
    int         id = 0;
    std::string client;     // "192.168.8.12"
    std::string path;       // "/v1/chat/completions"
    std::string asked;      // the last user message, a decision's state, or the prompt
    std::string answered;   // the text answered so far
    int         questions = 0;  // a decision request's questions, each one decision
    int         status = 0; // the HTTP status once done, 0 while it runs
    double      seconds = 0;  // how long it took, once done
    double      started = 0;  // steady clock, seconds
};

enum class ServerState : uint8_t { loading, ready, generating, failed, no_model };

struct ModelRow {
    std::string file;   // path
    std::string label;  // file name without .gguf
    std::string arch;
    std::string plan;   // the planner's line ("64k context, q8_0 cache: 9.9 of 11.0 GiB")
    std::string preset;     // the preset that filled its sampling ("Qwen 3.8"), or empty
    std::string decision;   // its decision type ("clef", "lfm2-d1"), empty for a language model
    double      size_gib = 0;
    bool        fits     = false;
    bool        current  = false;
    std::string drive;  // the Drive's name it is on; every drive loads alike
};

// 首页监控板：一个引擎一张卡。端口是写死的（8001 文字 / 8002 图像 / 8003 语音），
// 8004/8005 留给以后。没加载模型的引擎也在列表里 —— 界面按「已加载几个」动态分屏。
struct EngineCard {
    int         slot  = 0;      // 1..5：席位号，界面按它排序
    int         port  = 0;      // 8001..8005
    std::string name;           // "文字" / "图像" / "语音"
    std::string kind;           // text / picture / speech / video / reserved
    std::string state;          // 未配置 / 未启动 / 加载中 / 就绪 / 生成中 / 出错 / 预留
    std::string model;          // 模型文件全路径，空 = 没加载
    bool        reserved = false;
    // 模型是否真的加载进显存了。没加载时 model_gib 是「预计会占多少」（文件体积），
    // 不能算进已用内存 —— 否则三个引擎一凑就超过池子。
    bool        loaded   = false;  // 8004/8005：占位，不接请求
    std::string activity;       // 当前任务一行（界面拼好或引擎自报）
    double      model_gib = 0;  // 权重占的
    double      extra_gib = 0;  // 上下文缓存 / 中间缓冲
    // 文字
    float       tps      = 0;
    uint32_t    ctx      = 0;
    std::string kv_type;
    uint64_t    requests = 0;
    // 画图 / 视频
    int         step = 0, steps = 0;
    int         width = 0, height = 0, frames = 0, fps = 0;
    double      cfg = 0;
    std::string detail;         // 一行额外说明（客户端自己拼）
    // 语音
    std::string lang, voice;
};

struct Live {
    ServerState state = ServerState::loading;
    std::vector<EngineCard> engines;   // 首页监控板的五个槽位
    std::string address;     // "192.168.1.19:8081"（文字引擎）
    std::string host;        // "192.168.1.19"：端点页按引擎端口自己拼

    // The model that runs.
    std::string model_label;
    std::string model_arch;
    std::string preset;      // "Qwen 3.8"
    std::string decision;    // the decision type, empty for a language model
    double      model_gib = 0;
    uint32_t    ctx       = 0;
    std::string kv_type;
    double      kv_gib    = 0;
    std::string model_file;              // full path
    std::string plan;                    // the planner's line
    std::vector<std::string> args;       // llama-server's arguments

    // Speed.
    float gen_tps    = 0;    // over the last generation interval
    float prompt_tps = 0;    // last prompt
    std::vector<float> gen_history;   // tok/s per second, oldest first (0 while idle)
    std::vector<float> gpu_history;   // GPU busy 0..1 per second
    std::vector<float> cpu_history;   // CPU use 0..1 per second

    // Load.
    float gpu_busy = 0;      // 0..1
    float cpu_use  = 0;      // 0..1 of the CPUs the app may use
    int   cpus     = 0;

    // The console. Temperatures in degrees C, below -100 when unread; power
    // in watts, 0 when unread; the CPU clock in GHz.
    float soc_temp = -1000;
    float cpu_temp = -1000;
    float soc_power_w = 0;
    float cpu_ghz = 0;
    float fan = -1;              // fan duty 0..1, below 0 when unread
    bool  sensors_from_exporter = false;  // read from ps5-exporter, not the kernel
    std::vector<float> temp_history;  // SoC degrees C per second
    std::vector<float> power_history; // SoC watts per second
    // The same four over the last hour, a point per 30 seconds (their mean).
    std::vector<float> temp_hour, power_hour, gpu_hour, cpu_hour;
    double energy_wh = 0;             // SoC energy since the app started
    std::vector<std::pair<std::string, float>> temps;  // every sensor that answered ("cpu", "soc0", ...)

    // Storage: internal first, then the M.2 slot and USB drives that are mounted.
    std::vector<Drive> drives;
    double scratch_gib = 0;  // the chat tools' scratch folder

    // Memory, GiB.
    double pool_gib = 0;     // the title's direct memory
    double free_gib = 0;
    double heap_gib = 0;     // CPU heap, part of the pool

    // Loading: how much of the model and its cache is on the GPU, 0..1, or -1.
    float load_progress = -1;
    std::string phase;  // what the app does before the load can start ("Opening the GPU"), or empty

    // Session.
    double   uptime_s  = 0;
    uint64_t tokens    = 0;  // generated since start
    uint64_t prompt_tokens = 0;
    uint64_t requests  = 0;
    uint32_t ctx_used  = 0;  // in the running slot

    std::vector<ModelRow> models;
    std::vector<Exchange> activity;  // the latest requests, oldest first
    uint64_t served = 0;             // requests answered without an error
};

// The sampling thread. Fill the static parts (model, address) with set_*;
// snapshot() copies everything for the frame.
class StatsCollector {
  public:
    void start(int port);
    Live snapshot();
    void set_model(const Live & model_part);   // model_* , ctx, kv_*, preset
    void set_models(const std::vector<ModelRow> & rows);
    void set_engines(std::vector<EngineCard> cards);
    void set_state(ServerState s);
    void set_scratch(double gib);
    void set_phase(std::string phase);
    // From llama-server's HTTP threads, through activity.cpp.
    void activity_begin(int id, std::string client, std::string path, std::string asked, int questions);
    void activity_text(int id, const std::string & text);
    void activity_end(int id, int status);

  private:
    void run();
    std::mutex mutex_;
    Live       live_;
    double     load_base_ = -1;   // pool in use when the load began
    int        port_ = 8081;
};

// The console's address on the LAN, as the PC sees it ("192.168.1.19"), or
// empty. Asks the routing table through an unconnected UDP socket: nothing is sent.
// Sends a payload file to an ELF loader on this console; false if none listens.
// Internal storage, then each mounted M.2 or USB drive, with its space, from
// ps5-exporter's metrics (asked for here, or text already fetched).
std::vector<Drive> mounted_drives();
std::vector<Drive> drives_from_metrics(const std::string & text);

// The kind of drive holding `path`: "Internal storage", "M.2 drive", "USB drive".
std::string drive_name(const std::string & path);

bool send_payload(const char * path, int port);
// Where llama-server's request hooks (activity.cpp) report.
void set_activity_sink(StatsCollector * stats);

std::string local_address();

// A tiny HTTP GET over loopback; returns the body, or empty.
std::string http_get(int port, const char * path, int timeout_s = 1);
// The same with a JSON body, as a POST; reads the answer to its end.
std::string http_post(int port, const char * path, const std::string & body, int timeout_s);

// Asks the app's own server, as Home's Message and Demo do, on a thread of its
// own: a chat message, or for a decision model a text to decide on. It shows
// in the feed like any other request (activity.cpp).
void ask_self(int port, const std::string & text, bool decision);

// One value from Prometheus text ("llamacpp:tokens_predicted_total 42").
double metric(const std::string & text, const char * name);

// One sample from Prometheus text by its full name and labels, or `missing`.
double sample(const std::string & text, const std::string & key, double missing);

}  // namespace ps5lm
