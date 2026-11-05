#!/usr/bin/env python3
"""Put the video model set's other two files on the Settings page.

sd_server now keeps two sets: images (sd_diffusion/sd_clip_l/sd_vae) and video
(sd_video/sd_video_t5xxl/sd_video_vae). The TV page only knew about sd_video,
so the encoder and the VAE could only be set by editing settings.json over FTP.

    python3 patch-dashboard-video-set.py [--check|--revert]
"""
import sys
from pathlib import Path

TARGET = Path("/home/yk/PS5MM/ps5/app/dashboard.cpp")
EDITS = []


def edit(old: str, new: str, tag: str) -> None:
    EDITS.append((old, new, tag))


# 1) enum
edit(
    """    // the video engine
    sd_video, sd_frames, sd_fps,""",
    """    // the video engine
    sd_video, sd_video_t5xxl, sd_video_vae, sd_frames, sd_fps,""",
    "enum",
)

# 2) the rows themselves
edit(
    """      { { Setting::sd_video, "视频模型", "Wan 这类；留空就用图像那个" },
        { Setting::sd_frames, "帧数", "越多越长，显存吃得也越多" },
        { Setting::sd_fps, "帧率", "出片时每秒放几帧" },
        { Setting::max_frames, "帧数上限", "按剩余内存给的建议上限；超了多半 OOM" } },
      4 },""",
    """      { { Setting::sd_video, "视频模型", "Wan 这类；留空就用图像那个" },
        { Setting::sd_video_t5xxl, "视频编码器", "Wan 的文本（umt5）；留空沿用上面那个" },
        { Setting::sd_video_vae, "视频 VAE", "Wan 的 VAE；留空沿用上面那个" },
        { Setting::sd_frames, "帧数", "越多越长，显存吃得也越多" },
        { Setting::sd_fps, "帧率", "出片时每秒放几帧" },
        { Setting::max_frames, "帧数上限", "按剩余内存给的建议上限；超了多半 OOM" } },
      6 },""",
    "rows",
)

# 3) how the row is displayed
edit(
    """        case Setting::voices_dir:
        case Setting::sd_diffusion:
        case Setting::sd_video:
        case Setting::sd_clip_l:""",
    """        case Setting::voices_dir:
        case Setting::sd_diffusion:
        case Setting::sd_video:
        case Setting::sd_video_t5xxl:
        case Setting::sd_video_vae:
        case Setting::sd_clip_l:""",
    "display: case labels",
)
edit(
    """                                     : id == Setting::sd_video     ? s.sd_video
                                     : id == Setting::sd_clip_l    ? s.sd_clip_l""",
    """                                     : id == Setting::sd_video     ? s.sd_video
                                     : id == Setting::sd_video_t5xxl ? s.sd_video_t5xxl
                                     : id == Setting::sd_video_vae ? s.sd_video_vae
                                     : id == Setting::sd_clip_l    ? s.sd_clip_l""",
    "display: path lookup",
)
edit(
    """            if (path.empty()) {
                return id == Setting::sd_video ? "同图像模型" : "无";
            }""",
    """            if (path.empty()) {
                // 视频那一套的三行都能靠"沿用图像那套"过日子
                const bool video_row = id == Setting::sd_video || id == Setting::sd_video_t5xxl ||
                                       id == Setting::sd_video_vae;
                return video_row ? "同图像那套" : "无";
            }""",
    "display: empty text",
)

# 4) the picker
edit(
    """        case Setting::tts_mmproj:
        case Setting::sd_diffusion:
        case Setting::sd_video:
        case Setting::sd_clip_l:""",
    """        case Setting::tts_mmproj:
        case Setting::sd_diffusion:
        case Setting::sd_video:
        case Setting::sd_video_t5xxl:
        case Setting::sd_video_vae:
        case Setting::sd_clip_l:""",
    "picker: case labels",
)
edit(
    """            const bool sz          = id == Setting::sd_vae || id == Setting::sd_esrgan;""",
    """            const bool sz          = id == Setting::sd_vae || id == Setting::sd_video_vae ||
                                     id == Setting::sd_esrgan;""",
    "picker: sort by size",
)
edit(
    """                    case Setting::sd_diffusion: return v.sd_diffusion;
                    case Setting::sd_video:     return v.sd_video;""",
    """                    case Setting::sd_diffusion: return v.sd_diffusion;
                    case Setting::sd_video:     return v.sd_video;
                    case Setting::sd_video_t5xxl: return v.sd_video_t5xxl;
                    case Setting::sd_video_vae: return v.sd_video_vae;""",
    "picker: field",
)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--check":
        src = TARGET.read_text(encoding="utf-8")
        for old, new, tag in EDITS:
            print(f"{'applied' if new in src else ('todo' if old in src else 'MISSING'):8s} {tag}")
        return 0
    if mode == "--revert":
        src = TARGET.read_text(encoding="utf-8")
        for old, new, tag in reversed(EDITS):
            if new in src:
                src = src.replace(new, old, 1)
        TARGET.write_text(src, encoding="utf-8")
        print("reverted")
        return 0
    failed = False
    for old, new, tag in EDITS:
        src = TARGET.read_text(encoding="utf-8")
        if new in src:
            print(f"skip     {tag}")
            continue
        n = src.count(old)
        if n != 1:
            print(f"FAILED   {tag}: anchor x{n}", file=sys.stderr)
            failed = True
            continue
        TARGET.write_text(src.replace(old, new, 1), encoding="utf-8")
        print(f"patched  {tag}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
