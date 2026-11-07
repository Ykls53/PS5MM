#!/usr/bin/env python3
"""把 8004 从 audio.cpp 换成视频（sd.cpp 第二实例）。

背景：
  * audio.cpp 在 PS5 上从来没成功过（5 次卡死，family 字段永远是空）
  * 视频在 PS5 上跑出过结果，只是和图片互斥（12 GiB 装不下两套权重）
  * 用户自定义端口的能力必须保留：video_slot 和 picture_slot 走同一条路

改动：
  1. settings.hpp / .cpp  加 video_slot（默认 4）+ sd_video_* 已有字段
  2. main.cpp            删掉 audio 引擎启动，改成第二个 sd_server（视频模式）
  3. sd_server.hpp/.cpp  加 video_only 标志：决定默认用哪套模型
  4. dashboard 的音频卡改成视频卡

    python3 patch-video-slot.py [--check|--revert]
"""
import sys
from pathlib import Path

APP = Path("/home/yk/PS5MM/ps5/app")
EDITS = []


def edit(path, old, new, tag):
    EDITS.append((path, old, new, tag))


# ---------------------------------------------------------------- settings：加 video_slot
edit(
    APP / "settings.hpp",
    """    int         text_slot    = 1;
    int         picture_slot = 2;
    int         speech_slot  = 3;""",
    """    int         text_slot    = 1;
    int         picture_slot = 2;
    int         speech_slot  = 3;
    // 视频单独占一个槽位（8004 by default）。它和 picture_slot 走同一条
    // port_of_slot 路径，所以设置里照样能改端口。
    int         video_slot   = 4;""",
    "settings.hpp: video_slot",
)

edit(
    APP / "settings.cpp",
    """    s.speech_slot    = j.value("speech_slot", s.speech_slot);""",
    """    s.speech_slot    = j.value("speech_slot", s.speech_slot);
    s.video_slot     = j.value("video_slot", s.video_slot);""",
    "settings.cpp: load",
)

edit(
    APP / "settings.cpp",
    """        { "text_slot", s.text_slot }, { "picture_slot", s.picture_slot }, { "speech_slot", s.speech_slot },""",
    """        { "text_slot", s.text_slot }, { "picture_slot", s.picture_slot }, { "speech_slot", s.speech_slot },
        { "video_slot", s.video_slot },""",
    "settings.cpp: save",
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
