#!/usr/bin/env python3
# Add POST /unload to the sd (picture/video) and VoxCPM speech engines.
#   --check / --revert
import pathlib, sys, shutil

def patch(path, chunks, bak_suffix):
    p = pathlib.Path(path)
    bak = p.with_name(p.name + bak_suffix)
    src = p.read_text(encoding="utf-8")
    if "--revert" in sys.argv:
        if bak.exists():
            shutil.copyfile(bak, p)
            print("reverted", p.name)
        return
    if "--check" in sys.argv:
        for old, new in chunks:
            print(p.name, "OK  " if new in src else "MISS", new.splitlines()[0][:60])
        return
    for old, new in chunks:
        n = src.count(old)
        if n != 1:
            raise SystemExit(f"{p.name}: anchor matched {n}: {old.splitlines()[0][:60]}")
        src = src.replace(old, new)
    if not bak.exists():
        shutil.copyfile(p, bak)
    p.write_text(src, encoding="utf-8")
    print("patched", p.name)

# ---------------- sd_server.cpp ----------------
sd_chunks = [
(
'''void on_health(const httplib::Request &, httplib::Response & res) {
''',
'''// POST /unload — drop the picture/video model now, without leaving the app.
// The next generation request loads it again (ensure_ctx).
void on_unload(const httplib::Request &, httplib::Response & res) {
    std::lock_guard<std::mutex> lock(g_e.mu);
    const bool had = g_e.ctx != nullptr;
    if (g_e.ctx != nullptr) {
        free_sd_ctx(g_e.ctx);
        g_e.ctx = nullptr;
    }
    g_e.loaded_key.clear();
    g_e.ready     = false;
    g_want_video  = false;
    std::printf("ps5mm-sd: unloaded the model (had=%d)\\n", (int) had);
    std::fflush(nullptr);
    res.set_content(json{ { "ok", true }, { "engine", "picture" }, { "unloaded", had } }.dump(),
                    "application/json");
}

void on_health(const httplib::Request &, httplib::Response & res) {
''',
),
(
'''    g_svr.Get("/health", on_health);
    g_svr.Get("/sdapi/v1/options", on_options);
''',
'''    g_svr.Get("/health", on_health);
    g_svr.Post("/unload", on_unload);
    g_svr.Get("/sdapi/v1/options", on_options);
''',
),
(
'''    g_svr_video.Get("/health", on_health);
    g_svr_video.Post("/sdapi/v1/txt2vid", on_txt2vid);
''',
'''    g_svr_video.Get("/health", on_health);
    g_svr_video.Post("/unload", on_unload);
    g_svr_video.Post("/sdapi/v1/txt2vid", on_txt2vid);
''',
),
]
patch("/home/yk/PS5MM/ps5/app/sd_server.cpp", sd_chunks, ".bak-unload")

# ---------------- voxcpm_server.cpp ----------------
vox_chunks = [
(
'''void on_health(const httplib::Request &, httplib::Response & res) {
''',
'''// POST /unload — release the VoxCPM weights (about 1.5 GiB with the 0.5B q8_0).
void on_unload(const httplib::Request &, httplib::Response & res) {
    std::lock_guard<std::mutex> lock(g_e.mu);
    const bool had = (bool) g_e.core;
    g_e.core.reset();
    g_e.status = 0;
    std::printf("ps5mm-voxcpm: unloaded (had=%d)\\n", (int) had);
    std::fflush(nullptr);
    res.set_content(json{ { "ok", true }, { "engine", "voxcpm" }, { "unloaded", had } }.dump(),
                    "application/json");
}

void on_health(const httplib::Request &, httplib::Response & res) {
''',
),
(
'''    g_svr.Get("/health", on_health);
    g_svr.Get("/v1/audio/voices", on_voices);
''',
'''    g_svr.Get("/health", on_health);
    g_svr.Post("/unload", on_unload);
    g_svr.Get("/v1/audio/voices", on_voices);
''',
),
]
patch("/home/yk/PS5MM/ps5/app/voxcpm_server.cpp", vox_chunks, ".bak-unload")
