#!/usr/bin/env python3
"""修三处总览页显示问题。

1. 底部内存条和卡片挤在一起（卡片底边 856，横条 884，只隔 28px，视觉上交叉）
   -> 卡片收到 832，横条下移到 876 且更细，图例跟着上移
2. 卡 2（图像）把图片尺寸和视频帧数混着显示：「256×256 · 5 帧 · 1 步」
   -> 按 kind 分开：图片只写尺寸+步数，视频才写帧数
3. 卡 2 的「生成中」用的是 sd 全局状态，跑视频时也显示在图片卡上
   -> 保留（两个口共用一套上下文，确实是同一个引擎在忙），但 detail 文字要说清

    python3 patch-dashboard-fix.py [--check|--revert]
"""
import sys
from pathlib import Path

D = Path("/home/yk/PS5MM/ps5/app/dashboard.cpp")
EDITS = []


def edit(old, new, tag):
    EDITS.append((old, new, tag))


# 1. 卡片区域收窄，给底部横条腾地方
edit(
    """    constexpr int   kStrips = 5;
    const float     top = 214, bottom = 856;""",
    """    constexpr int   kStrips = 5;
    // bottom 从 856 收到 836：下面那条内存总线在 884，原来只隔 28px，
    // 卡片里的纵向推子和横条在视觉上贴住/交叉。
    const float     top = 214, bottom = 836;""",
    "card bottom 856 -> 836",
)

# 2. 底部分隔线也跟着上移一点点（原来在 884 的那条总线本身不动，但图例要挪）
edit(
    """    // 底部：内存总线。五个席位的占用按模态色分段，谁吃了多少一目了然。
    const Rect bar{ kLeft, 884, kRight - kLeft, 28 };""",
    """    // 底部：内存总线。横向一条，高度从 28 收到 18，位置下移到 892，
    // 和上面的卡片拉开距离（卡片底边 836）。
    const Rect bar{ kLeft, 892, kRight - kLeft, 18 };""",
    "memory bar 884/28 -> 892/18",
)

# 3. 图例位置跟着调
edit(
    """            l.rounded_rect({ lx, bar.y + 44, 12, 12 }, 3, mod_color(c.kind));
            lx += 20;
            char part[64];
            std::snprintf(part, sizeof part, "%s %.1f", c.name.c_str(), gib);
            lx += put(l, f.regular, part, lx, bar.y + 56, 19, kInk3) + 26;""",
    """            l.rounded_rect({ lx, bar.y + 30, 10, 10 }, 3, mod_color(c.kind));
            lx += 18;
            char part[64];
            std::snprintf(part, sizeof part, "%s %.1f", c.name.c_str(), gib);
            lx += put(l, f.regular, part, lx, bar.y + 38, 18, kInk3) + 24;""",
    "legend follows bar",
)

edit(
    """        l.rounded_rect({ lx, bar.y + 44, 12, 12 }, 3, kHair);
        lx += 20;
        char rest[64];
        std::snprintf(rest, sizeof rest, "空闲 %.1f GB", std::max(0.0, live_.pool_gib - used));
        put(l, f.regular, rest, lx, bar.y + 56, 19, kInk3);""",
    """        l.rounded_rect({ lx, bar.y + 30, 10, 10 }, 3, kHair);
        lx += 18;
        char rest[64];
        std::snprintf(rest, sizeof rest, "空闲 %.1f GB", std::max(0.0, live_.pool_gib - used));
        put(l, f.regular, rest, lx, bar.y + 38, 18, kInk3);""",
    "free legend follows bar",
)

# 4. 图片卡不再显示「帧」，视频卡才显示
edit(
    """        } else if (kind == "picture" && c->width > 0) {
            std::snprintf(line, sizeof line, "%d×%d · %d 帧 · %d 步", c->width, c->height, c->frames, c->steps);
            put(l, f.regular, line, r.x + 34, ay, 20, kInk3);""",
    """        } else if (kind == "picture" && c->width > 0) {
            // 图片只说尺寸和步数。帧数是视频的属性，混进图片卡会让人看不明白
            // （实测：256×256 的图片，卡上写着「5 帧」）。
            std::snprintf(line, sizeof line, "%d×%d · %d 步", c->width, c->height, c->steps);
            put(l, f.regular, line, r.x + 34, ay, 20, kInk3);""",
    "picture line: drop frames",
)

# 5. 补一个 video 分支（原来没有，视频卡什么都不显示）
edit(
    """        } else if (kind == "speech" && !c->lang.empty()) {""",
    """        } else if (kind == "video" && c->width > 0) {
            std::snprintf(line, sizeof line, "%d×%d · %d 帧 · %d 步", c->width, c->height, c->frames,
                          c->steps);
            put(l, f.regular, line, r.x + 34, ay, 20, kInk3);
        } else if (kind == "speech" && !c->lang.empty()) {""",
    "video line: size + frames",
)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = D.read_text(encoding="utf-8")
    if mode == "--check":
        for old, new, tag in EDITS:
            print(f"{'applied' if new in src else ('todo' if old in src else 'MISSING'):8s} {tag}")
        return 0
    if mode == "--revert":
        for old, new, tag in reversed(EDITS):
            if new in src:
                src = src.replace(new, old, 1)
        D.write_text(src, encoding="utf-8")
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
    D.write_text(src, encoding="utf-8")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
