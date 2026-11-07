#!/usr/bin/env python3
"""让 sd_server 告诉外面「这次跑的是图片还是视频」，卡片的「生成中」才能分对人。

现状：图片卡和视频卡都读同一个 sd_server_progress()，跑视频时图片卡也显示
「生成中」，而且图片卡还带着视频的帧数。

    python3 patch-sd-video-active.py [--check|--revert]
"""
import sys
from pathlib import Path

APP = Path("/home/yk/PS5MM/ps5/app")
EDITS = []


def edit(path, old, new, tag):
    EDITS.append((path, old, new, tag))


# ---- hpp：加查询
edit(
    APP / "sd_server.hpp",
    """void sd_server_progress(int * step, int * steps);   // 当前这一步 / 总共几步（0/0 = 没在跑）""",
    """void sd_server_progress(int * step, int * steps);   // 当前这一步 / 总共几步（0/0 = 没在跑）
// 当前（或最近一次）生成是视频还是图片。图片和视频共用一套 sd 上下文，
// 光看 progress 分不出谁在跑，界面要靠它决定哪张卡显示「生成中」。
bool sd_server_video_active(void);""",
    "hpp: video_active",
)

# ---- cpp：记一个原子标志
edit(
    APP / "sd_server.cpp",
    """std::atomic<bool> g_stop{ false };""",
    """std::atomic<bool> g_stop{ false };
// 最近一次 ensure_ctx 要的是视频还是图片。生成期间界面靠它分辨谁在忙。
std::atomic<bool> g_want_video{ false };""",
    "cpp: g_want_video",
)

edit(
    APP / "sd_server.cpp",
    """void sd_server_progress(int * step, int * steps) {""",
    """bool sd_server_video_active(void) { return g_want_video.load(); }

void sd_server_progress(int * step, int * steps) {""",
    "cpp: video_active impl",
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
