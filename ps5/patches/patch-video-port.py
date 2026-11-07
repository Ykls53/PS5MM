#!/usr/bin/env python3
"""audio_server 的残留引用清掉，8004 改成视频入口。

三处改动：
  1. sd_server.hpp  加 sd_server_start_video(port)
  2. sd_server.cpp  第二个 httplib::Server 只挂 /health + /sdapi/v1/txt2vid，
                    共用同一个 g_e 和同一把 g_e.mu（图片和视频本来就物理互斥）
  3. main.cpp       音频卡换成视频卡；引擎过滤里 audio_slot 换成 video_slot

    python3 patch-video-port.py [--check|--revert]
"""
import sys
from pathlib import Path

APP = Path("/home/yk/PS5MM/ps5/app")
EDITS = []


def edit(path, old, new, tag):
    EDITS.append((path, old, new, tag))


# ---------------------------------------------------------------- hpp
edit(
    APP / "sd_server.hpp",
    """int  sd_server_start(const SdModels & models, int port);""",
    """int  sd_server_start(const SdModels & models, int port);

// 视频专用入口（8004）。和 sd_server_start 共用同一个 sd 上下文：
// 12 GiB 装不下图片和视频两套权重，所以它们本来就只能串行；这里只是把
// 「视频」这条路单独挂在另一个端口上，让前端有个清楚的入口。
// 忙的时候 pre_routing_handler 会返回 503，不会把请求排死。
int  sd_server_start_video(int port);""",
    "hpp: start_video",
)

# ---------------------------------------------------------------- cpp: 第二个 server
edit(
    APP / "sd_server.cpp",
    """httplib::Server   g_svr;
std::thread       g_thread;""",
    """httplib::Server   g_svr;
std::thread       g_thread;
// 视频专用监听（8004）。共用 g_e，共用 g_e.mu。
httplib::Server   g_svr_video;
std::thread       g_thread_video;""",
    "cpp: video globals",
)

edit(
    APP / "sd_server.cpp",
    """void sd_server_terminate(void) {
    if (g_stop.exchange(true)) {
        return;
    }
    g_svr.stop();""",
    """int sd_server_start_video(int port) {
    // 只挂视频那一条 + 探活。图片、媒体、插帧仍然只在主口上。
    g_svr_video.Get("/health", on_health);
    g_svr_video.Post("/sdapi/v1/txt2vid", on_txt2vid);
    g_svr_video.set_pre_routing_handler([](const httplib::Request & req, httplib::Response & res) {
        if (req.path == "/health") {
            return httplib::Server::HandlerResponse::Unhandled;
        }
        if (g_load_stuck.load()) {
            res.status = 503;
            res.set_content(R"({"error":"上次加载超时，已放弃；重启 PS5MM 再来一次"})", "application/json");
            return httplib::Server::HandlerResponse::Handled;
        }
        if (g_loading.load()) {
            res.status = 503;
            res.set_content(R"({"error":"model is loading, retry later"})", "application/json");
            return httplib::Server::HandlerResponse::Handled;
        }
        return httplib::Server::HandlerResponse::Unhandled;
    });
    g_svr_video.set_read_timeout(120, 0);
    g_svr_video.set_write_timeout(3600, 0);   // 一条 33 帧的片子是分钟级
    g_svr_video.set_payload_max_length(4 * 1024 * 1024);
    std::printf("ps5mm-sd: video routes on :%d (same context as the picture port)\\n", port);
    std::fflush(nullptr);
    g_thread_video = std::thread([port] {
        if (!g_svr_video.listen("0.0.0.0", port)) {
            std::printf("ps5mm-sd: could not listen on %d (video)\\n", port);
            std::fflush(nullptr);
        }
    });
    return 0;
}

void sd_server_terminate(void) {
    if (g_stop.exchange(true)) {
        return;
    }
    g_svr_video.stop();
    if (g_thread_video.joinable()) {
        g_thread_video.detach();
    }
    g_svr.stop();""",
    "cpp: start_video + terminate",
)

# ---------------------------------------------------------------- main.cpp: 卡片
edit(
    APP / "main.cpp",
    """        // 音频引擎卡：占第一个没被三个真引擎用掉的槽位。
        {
            int audio_slot = 0;
            for (int s = 1; s <= 5; ++s) {
                if (s != st.text_slot && s != st.picture_slot && s != st.speech_slot) {
                    audio_slot = s;
                    break;
                }
            }
            if (audio_slot != 0) {
                EngineCard c;
                c.slot   = audio_slot;
                c.port   = ps5mm::port_of_slot(audio_slot);
                c.name   = "音频";
                c.kind   = "audio";
                c.state  = audio_server_ready()     ? "就绪"
                         : audio_server_listening() ? "等请求"
                                                    : "未启动";
                c.detail = audio_server_family().empty() ? "130+ 音频家族" : audio_server_family();
                if (audio_server_last_ms() > 0) {
                    c.activity = std::to_string(audio_server_last_ms()) + " ms";
                }
                cards.push_back(std::move(c));
            }
        }""",
    """        // 视频引擎卡：和图片共用 sd 上下文，但端口独立。
        {
            EngineCard c;
            c.slot     = st.video_slot;
            c.port     = ps5mm::port_of_slot(st.video_slot);
            c.name     = "视频";
            c.kind     = "video";
            c.state    = sd_server_listening() ? "等请求" : "未启动";
            c.model    = st.sd_video;
            c.loaded   = false;
            c.model_gib = file_gib(st.sd_video) + file_gib(st.sd_video_t5xxl) + file_gib(st.sd_video_vae);
            c.detail   = "和图片共用一套 sd 上下文（12 GiB 装不下两套）";
            cards.push_back(std::move(c));
        }""",
    "main: audio card -> video card",
)

edit(
    APP / "main.cpp",
    """            // 音频引擎也占一个空闲槽位，跳开它。
            {
                int audio_slot = 0;
                for (int q = 1; q <= 5; ++q) {
                    if (q != st.text_slot && q != st.picture_slot && q != st.speech_slot) {
                        audio_slot = q;
                        break;
                    }
                }
                if (s == audio_slot) {
                    continue;
                }
            }""",
    """            // 视频槽位也是真引擎，跳开它。
            if (s == st.video_slot) {
                continue;
            }""",
    "main: reserved filter",
)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--check":
        for path, old, new, tag in EDITS:
            src = path.read_text(encoding="utf-8")
            print(f"{'applied' if new in src else ('todo' if old in src else 'MISSING'):8s} {tag}")
        return 0
    if mode == "--revert":
        for path, old, new, tag in reversed(EDITS):
            src = path.read_text(encoding="utf-8")
            if new in src:
                path.write_text(src.replace(new, old, 1), encoding="utf-8")
        print("reverted")
        return 0
    failed = False
    for path, old, new, tag in EDITS:
        src = path.read_text(encoding="utf-8")
        if new in src:
            print(f"skip     {tag}")
            continue
        if src.count(old) != 1:
            print(f"FAILED   {tag}: anchor x{src.count(old)}", file=sys.stderr)
            failed = True
            continue
        path.write_text(src.replace(old, new, 1), encoding="utf-8")
        print(f"patched  {tag}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
