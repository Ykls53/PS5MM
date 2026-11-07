#!/usr/bin/env python3
"""把视频口接进 main.cpp 的启动流程，并拔掉 audio 的 include。

启动位置：3D 引擎之前（和原来的音频位置一致）。
"""
import sys
from pathlib import Path

MAIN = Path("/home/yk/PS5MM/ps5/app/main.cpp")
EDITS = []


def edit(old, new, tag):
    EDITS.append((old, new, tag))


# 1. 拔掉 audio_server.hpp（不再用了，留着链接不到符号也无所谓，但干净点）
edit(
    '#include "audio_server.hpp"\n',
    "",
    "drop audio_server.hpp include",
)

# 2. 起视频口：接在「音频引擎已移除」那段注释后面
edit(
    """        //   代码和 .deps/audio-acx 都留着，需要时能随时接回来。

        // 3D 引擎：TRELLIS.2 图生 3D（TRX_ 前缀），占 video 之后的下一个空闲槽位。""",
    """        //   代码和 .deps/audio-acx 都留着，需要时能随时接回来。

        // 视频入口：和图片共用同一个 sd 上下文（12 GiB 装不下两套权重），
        // 但挂在独立端口上，前端能分开调。忙的时候 503，不会把请求排死。
        {
            const int video_port = ps5mm::port_of_slot(boot.video_slot);
            std::printf("ps5mm-app: video route on :%d\\n", video_port);
            std::fflush(nullptr);
            sd_server_start_video(video_port);
        }

        // 3D 引擎：TRELLIS.2 图生 3D（TRX_ 前缀），占 video 之后的下一个空闲槽位。""",
    "start video port",
)

# 3. 3D 槽位计算要跳过 video_slot（原来跳过 audio 的位置）
edit(
    """            int slot3d = 0;
            int taken  = 0;
            for (int s = 1; s <= 5; ++s) {
                if (s == boot.text_slot || s == boot.picture_slot || s == boot.speech_slot) {
                    continue;
                }""",
    """            int slot3d = 0;
            int taken  = 0;
            for (int s = 1; s <= 5; ++s) {
                if (s == boot.text_slot || s == boot.picture_slot || s == boot.speech_slot ||
                    s == boot.video_slot) {
                    continue;
                }""",
    "3D slot skips video",
)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = MAIN.read_text(encoding="utf-8")
    if mode == "--check":
        for old, new, tag in EDITS:
            print(f"{'applied' if new in src else ('todo' if old in src else 'MISSING'):8s} {tag}")
            src = MAIN.read_text(encoding="utf-8")
        return 0
    if mode == "--revert":
        src = MAIN.read_text(encoding="utf-8")
        for old, new, tag in reversed(EDITS):
            if new in src:
                src = src.replace(new, old, 1)
        MAIN.write_text(src, encoding="utf-8")
        print("reverted")
        return 0
    failed = False
    for old, new, tag in EDITS:
        if new and new in src:
            print(f"skip     {tag}")
            continue
        if src.count(old) != 1:
            print(f"FAILED   {tag}: anchor x{src.count(old)}", file=sys.stderr)
            failed = True
            continue
        src = src.replace(old, new, 1)
        print(f"patched  {tag}")
    MAIN.write_text(src, encoding="utf-8")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
