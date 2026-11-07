#!/usr/bin/env python3
"""两张卡按 sd_server_video_active() 分开显示。

图片卡：只有「跑的是图片」才显示生成中，而且不再带视频的帧数。
视频卡：跑视频时显示生成中 + 尺寸/帧数/步数；平时显示等请求。
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")
EDITS = []


def edit(old, new, tag):
    EDITS.append((old, new, tag))


# ---- 图片卡：状态区分 + 去掉 frames
edit(
    """            int step = 0, steps = 0;
            sd_server_progress(&step, &steps);
            const bool live_route = sd_server_listening();
            const bool loaded     = sd_server_ready();
            c.state   = st.sd_diffusion.empty() ? "未配置"
                      : !live_route             ? "未启动"
                      : step > 0 && steps > 0   ? "生成中"
                      : loaded                  ? "就绪"
                                                : "等第一次请求";""",
    """            int step = 0, steps = 0;
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
                                               : "等第一次请求";""",
    "picture card: busy only when image",
)

edit(
    """            c.step      = step;
            c.steps     = steps;
            c.width     = (int) st.sd_width;
            c.height    = (int) st.sd_height;
            c.frames    = st.sd_frames;
            c.fps       = st.sd_fps;""",
    """            c.step      = busy_picture ? step : 0;
            c.steps     = busy_picture ? steps : 0;
            c.width     = (int) st.sd_width;
            c.height    = (int) st.sd_height;
            c.frames    = 0;   // 帧数是视频的属性，别混进图片卡
            c.fps       = 0;""",
    "picture card: no frames",
)

# ---- 视频卡：跟着进度动
edit(
    """            c.kind     = "video";
            c.state    = sd_server_listening() ? "等请求" : "未启动";
            c.model    = st.sd_video;
            c.loaded   = false;
            c.model_gib = file_gib(st.sd_video) + file_gib(st.sd_video_t5xxl) + file_gib(st.sd_video_vae);
            c.detail   = "和图片共用一套 sd 上下文（12 GiB 装不下两套）";""",
    """            c.kind     = "video";
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
                                    : "和图片共用一套 sd 上下文（12 GiB 装不下两套）";""",
    "video card: live progress",
)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = M.read_text(encoding="utf-8")
    if mode == "--check":
        for old, new, tag in EDITS:
            print(f"{'applied' if new in src else ('todo' if old in src else 'MISSING'):8s} {tag}")
        return 0
    if mode == "--revert":
        for old, new, tag in reversed(EDITS):
            if new in src:
                src = src.replace(new, old, 1)
        M.write_text(src, encoding="utf-8")
        print("reverted")
        return 0
    failed = False
    for old, new, tag in EDITS:
        if new in src:
            print(f"skip     {tag}")
            continue
        if src.count(old) != 1:
            print(f"FAILED   {tag}: anchor x{src.count(old)}", file=sys.stderr)
            failed = True
            continue
        src = src.replace(old, new, 1)
        print(f"patched  {tag}")
    M.write_text(src, encoding="utf-8")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
