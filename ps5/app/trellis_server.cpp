// SPDX-License-Identifier: GPL-3.0-or-later
// PS5MM's 3D engine: TRELLIS.2 (image -> 3D) on its own ggml and Vulkan
// backend, in the same process as the other engines.
//
// Routes:
//   POST /v1/images/to3d    { image: <base64 png/jpg>, seed?, resolution?, faces? }
//                           -> { glb: <base64>, saved: <path>, ms: n }
//   GET  /health
//
// One run at a time: the pipeline holds the whole flow transformer resident for
// the length of a run, so a second request waits on the mutex rather than
// doubling the memory.

#include "trellis_server.hpp"

#include "trellis_args.h"
#include "trellis_run.h"

#include "cpp-httplib/httplib.h"
#include "nlohmann/json.hpp"

#include <sys/stat.h>

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <fstream>
#include <mutex>
#include <new>
#include <string>
#include <thread>
#include <vector>

namespace {

using json = nlohmann::json;

struct Engine {
    std::string       models;
    std::string       out_dir;
    std::string       backend;
    std::mutex        mu;
    std::atomic<long> jobs{ 0 };
    std::atomic<long> last_ms{ 0 };
    std::atomic<bool> listening{ false };
};

Engine            g_t;
httplib::Server * g_svr = nullptr;

std::string b64_decode(const std::string & b64) {
    std::string raw;
    raw.reserve(b64.size() * 3 / 4 + 3);
    unsigned acc = 0;
    int      bits = 0;
    for (char c : b64) {
        int v = -1;
        if (c >= 'A' && c <= 'Z') v = c - 'A';
        else if (c >= 'a' && c <= 'z') v = c - 'a' + 26;
        else if (c >= '0' && c <= '9') v = c - '0' + 52;
        else if (c == '+') v = 62;
        else if (c == '/') v = 63;
        else continue;
        acc = (acc << 6) | (unsigned) v;
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            raw.push_back((char) ((acc >> bits) & 0xFF));
        }
    }
    return raw;
}

std::string b64_encode(const unsigned char * p, size_t n) {
    static const char * t = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    out.reserve((n + 2) / 3 * 4);
    for (size_t i = 0; i < n; i += 3) {
        const unsigned v = (unsigned) p[i] << 16 |
                           (i + 1 < n ? (unsigned) p[i + 1] << 8 : 0u) |
                           (i + 2 < n ? (unsigned) p[i + 2] : 0u);
        out.push_back(t[(v >> 18) & 63]);
        out.push_back(t[(v >> 12) & 63]);
        out.push_back(i + 1 < n ? t[(v >> 6) & 63] : '=');
        out.push_back(i + 2 < n ? t[v & 63] : '=');
    }
    return out;
}

bool write_file(const std::string & path, const void * data, size_t n) {
    std::FILE * f = std::fopen(path.c_str(), "wb");
    if (f == nullptr) {
        return false;
    }
    const size_t wrote = std::fwrite(data, 1, n, f);
    std::fclose(f);
    return wrote == n;
}

bool read_file(const std::string & path, std::string & out) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        return false;
    }
    out.assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
    return !out.empty();
}

void send_error(httplib::Response & res, int code, const std::string & msg) {
    res.status = code;
    res.set_content(json{ { "error", msg } }.dump(), "application/json");
}

void on_health(const httplib::Request &, httplib::Response & res) {
    json out{ { "ok", true },
              { "engine", "trellis" },
              { "models", g_t.models },
              { "jobs", (long) g_t.jobs.load() },
              { "last_ms", (long) g_t.last_ms.load() } };
    res.set_content(out.dump(), "application/json");
}

void on_to3d(const httplib::Request & req, httplib::Response & res) {
    json body;
    try {
        body = json::parse(req.body);
    } catch (const std::exception & e) {
        send_error(res, 400, std::string("bad JSON: ") + e.what());
        return;
    }
    const std::string b64 = body.value("image", std::string());
    if (b64.empty()) {
        send_error(res, 400, "give image (base64 png/jpg)");
        return;
    }
    const std::string raw = b64_decode(b64);
    if (raw.empty()) {
        send_error(res, 400, "the image decoded to nothing");
        return;
    }

    std::lock_guard<std::mutex> lock(g_t.mu);
    const long job = ++g_t.jobs;

    // trellis_run takes a path, not a buffer: stage the picture next to the output.
    char in_name[256];
    std::snprintf(in_name, sizeof in_name, "%s/to3d-in-%ld.png", g_t.out_dir.c_str(), job);
    if (!write_file(in_name, raw.data(), raw.size())) {
        send_error(res, 500, "could not stage the picture");
        return;
    }

    char out_name[256];
    std::snprintf(out_name, sizeof out_name, "%s/to3d-%ld.glb", g_t.out_dir.c_str(), job);

    trellis::TrellisParams p;
    p.image   = in_name;
    p.output  = out_name;
    p.models  = g_t.models;
    p.backend = g_t.backend;
    p.seed    = (uint32_t) body.value("seed", 0);
    if (body.contains("resolution")) {
        const int r = body.value("resolution", 1024);
        p.cascade = r >= 1024;
        if (!p.cascade) {
            p.hr_res = 512;
        } else if (r == 1536) {
            p.hr_res = 1536;
        }
    }
    p.naf = body.value("naf", true);
    // -- faces / decim -------------------------------------------------------
    // Both live on TrellisParams (trellis_args.h:79/80) and were documented in
    // the header comment above, but never forwarded. decim >= 0 bypasses the
    // QEM simplifier entirely (which segfaults on this machine), decim == 0
    // keeps the dense mesh, faces > 0 overrides the QEM face target.
    if (body.contains("faces")) {
        p.faces = body.value("faces", -1);
    }
    if (body.contains("decim")) {
        p.decim = body.value("decim", -1);
    }

    const int64_t t0 = (int64_t) (std::clock() * 1000 / CLOCKS_PER_SEC);
    std::printf("ps5mm-trellis: run %ld: %s -> %s\n", job, in_name, out_name);
    std::fflush(nullptr);

    // trellis_run() throws on allocation failure and can take a long time; an
    // uncaught bad_alloc here would abort the whole app (every other engine
    // goes down with it). Catch and report instead, so 8005 failing stays a
    // 8005 failure.
    int rc = -1;
    try {
        rc = trellis_run(p);
    } catch (const std::bad_alloc &) {
        std::remove(in_name);
        send_error(res, 507, "the 3D engine ran out of memory; retry with a smaller "
                             "resolution or a coarser decim");
        return;
    } catch (const std::exception & e) {
        std::remove(in_name);
        send_error(res, 500, std::string("the 3D engine threw: ") + e.what());
        return;
    } catch (...) {
        std::remove(in_name);
        send_error(res, 500, "the 3D engine threw an unknown exception");
        return;
    }

    const int64_t t1 = (int64_t) (std::clock() * 1000 / CLOCKS_PER_SEC);
    g_t.last_ms = (long) (t1 - t0);
    std::remove(in_name);

    if (rc != 0) {
        send_error(res, 500, "the 3D run failed (rc " + std::to_string(rc) + "), see app.log");
        return;
    }
    std::string glb;
    if (!read_file(out_name, glb)) {
        send_error(res, 500, "the run finished but produced no .glb");
        return;
    }
    std::printf("ps5mm-trellis: run %ld done, %zu bytes in %ld ms\n", job, glb.size(),
                (long) g_t.last_ms.load());
    std::fflush(nullptr);
    res.set_content(json{ { "glb", b64_encode((const unsigned char *) glb.data(), glb.size()) },
                          { "saved", out_name },
                          { "ms", (long) g_t.last_ms.load() } }
                        .dump(),
                    "application/json");
}

}  // namespace

int trellis_server_start(const TrellisPaths & paths, int port) {
    if (paths.models != nullptr) {
        g_t.models = paths.models;
    }
    if (paths.output_dir != nullptr) {
        g_t.out_dir = paths.output_dir;
    }
    if (paths.backend != nullptr) {
        g_t.backend = paths.backend;
    }
    mkdir(g_t.out_dir.c_str(), 0777);

    auto * svr = new httplib::Server();
    svr->Get("/health", on_health);
    svr->Post("/v1/images/to3d", on_to3d);
    g_svr = svr;

    std::thread([port]() {
        g_t.listening = true;
        std::printf("ps5mm-trellis: listening on :%d\n", port);
        std::fflush(nullptr);
        if (!g_svr->listen("0.0.0.0", port)) {
            std::printf("ps5mm-trellis: could not listen on :%d\n", port);
            std::fflush(nullptr);
            g_t.listening = false;
        }
    }).detach();

    return 0;
}

void trellis_server_terminate(void) {
    if (g_svr != nullptr) {
        g_svr->stop();
    }
}

bool trellis_server_listening(void) { return g_t.listening.load(); }

long trellis_server_last_ms(void) { return g_t.last_ms.load(); }
