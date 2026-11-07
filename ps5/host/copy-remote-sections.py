#!/usr/bin/env python3
"""把「远程操作 PS5」那套基础设施复制一份进 ps5mm 技能。

注意是**复制**，不是搬走 —— ps5-linux-maintain 里保留原样（那边讲 PS5LM/Linux 也要用）。
代价是双份：以后改这些章节，两个文件都要改。

    python3 copy-remote-sections.py [--dry]
"""
import sys
from pathlib import Path

SRC = Path(r"C:\Users\Yk\.agents\skills\ps5-linux-maintain\SKILL.md")
DST = Path(r"C:\Users\Yk\.agents\skills\ps5mm\SKILL.md")

# 要复制的章节（按二级标题前缀匹配）
WANT = (
    "## 🔴 重启代价极大",
    "## 🔴 探测 PS5 端口必须先绕过 TUN",
    "## 🔴 `shadowmount: failed`",
    "## 🔴 WebKit Autoloader 是纯离线的",
    "## 🔴 PS5 越狱后千万不能联网",
    "## 🔴 越狱不持久",
    "## 📸 从 PS5 相册捞截图",
    "## 🔌 ps5debug-NG 协议",
)

BANNER = """

---

# 远程操作 PS5（从 ps5-linux-maintain 复制过来的）

> 这 8 节是「怎么远程碰那台机器」的公共基础设施，PS5LM / PS5SD / PS5MM 都要用。
> **原件在 `ps5-linux-maintain` 里也有**；改的时候两边一起改，别只改一份。
"""


def slice_sections(text, prefixes):
    lines = text.splitlines(keepends=True)
    heads = [(i, l) for i, l in enumerate(lines) if l.startswith("## ")]
    heads.append((len(lines), ""))
    out = []
    for k in range(len(heads) - 1):
        start, title = heads[k]
        end = heads[k + 1][0]
        if any(title.startswith(p) for p in prefixes):
            out.append((start, end, title.rstrip(), "".join(lines[start:end])))
    return out


def main() -> int:
    dry = "--dry" in sys.argv
    src_text = SRC.read_text(encoding="utf-8")
    dst_text = DST.read_text(encoding="utf-8")

    picked = slice_sections(src_text, WANT)
    print(f"源文件 {len(src_text)} 字符，找到 {len(picked)}/{len(WANT)} 节：")
    total = 0
    for s, e, t, body in picked:
        print(f"  {s+1:>5}-{e:<5} ({e-s:>4} 行, {len(body):>6} 字符) {t[:62]}")
        total += len(body)
    missing = [p for p in WANT if not any(t.startswith(p) for _, _, t, _ in picked)]
    if missing:
        print("\n没找到：")
        for m in missing:
            print("  ", m)
    print(f"\n合计搬运 {total} 字符")

    if dry:
        return 0

    add = BANNER + "".join(body for _, _, _, body in picked)
    if "远程操作 PS5（从 ps5-linux-maintain 复制过来的）" in dst_text:
        print("ps5mm 里已经有这一节了，先手动删掉再加")
        return 2

    DST.write_text(dst_text.rstrip() + "\n" + add, encoding="utf-8")
    print(f"\n写出 {DST} ({(DST).stat().st_size} 字节)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
