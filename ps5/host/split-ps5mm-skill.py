#!/usr/bin/env python3
"""把 PS5MM（应用开发那条线）从 ps5-linux-maintain 里拆出来，单独建一个 skill。

不靠手抄：按行号区间整段搬，搬完再核对字符数，避免漏章、错位。
被搬走的区间以二级标题（## ）为界，不切断章节。

    python3 split-ps5mm-skill.py [--dry]
"""
import re
import sys
from pathlib import Path

SRC = Path(r"C:\Users\Yk\.agents\skills\ps5-linux-maintain\SKILL.md")
DST_DIR = Path(r"C:\Users\Yk\.agents\skills\ps5mm")

# 这些二级标题开头的章节搬去新技能（PS5MM 应用开发线）
MOVE_PREFIX = (
    "## 🎛 PS5MM",
    "## 🔴 PS5MM",
    "## 🧪 PS5MM",
    "## 🖥 PS5MM",
    "## ★ 破解 TacHen",
    "## 2026-11-04 夜：",
    "## 2026-11-04 深夜：",
    "## 🔴 TacHen `interrupted` 死锁",
    "## 🔴🔴 一次只能加载一个模型",
    "## 🔧 编 PS5 title 时 ps5-opengl",
    "## ✅ 已验证：EGL teardown",
    "## 🧰 工具坑",
)

HEADER = """---
name: ps5mm
description: 开发 / 维护 PS5MM 这个 PS5 原生应用（titleId PPSA99577，单进程跑七个引擎：文字 llama.cpp 8001、图片 sd.cpp 8002、语音 Qwen3-TTS 8003、音频 audio.cpp 8004、3D trellis 8005、插帧 RIFE、控制 8099）。主人说「PS5MM」「七引擎」「PS5 上那个应用」「PS5 语音」「PS5 文字模型」「给 PS5 加引擎」「PS5 画图/3D」「PS5 应用卡死」「PS5MM 部署」「PS5MM 编译」时触发。含：内存池与参数、七引擎实测状态、部署三步、一次只加载一个模型的铁律、卡死与退出、TacHen 远程启动与 interrupted 死锁、trellis 崩溃与 decoy、pc 侧验证法、已知坑与基线。
---

# PS5MM：PS5 原生七引擎应用

主人要的东西：**文字模型压上下文 + 实时语音对话**，两个口是核心（8001 / 8003）。
图片、视频、3D、插帧、音频是「顺便还能干这些」，不是核心。

已知可用基线、不许动的值、一次上机纪律，看项目根目录的
`D:\\deepseekDAIGirlfriend\\BASELINE.md`（每轮开工先读那一页）。

"""


def main() -> int:
    dry = "--dry" in sys.argv
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

    # 找所有二级标题的位置
    heads = [(i, l) for i, l in enumerate(lines) if l.startswith("## ")]
    heads.append((len(lines), ""))

    move_blocks = []   # [(start, end, title)]
    keep_mask = [True] * len(lines)

    for k in range(len(heads) - 1):
        start, title = heads[k]
        end = heads[k + 1][0]
        if any(title.startswith(p) for p in MOVE_PREFIX):
            move_blocks.append((start, end, title.rstrip()))
            for i in range(start, end):
                keep_mask[i] = False

    print(f"总行数 {len(lines)}，识别到 {len(move_blocks)} 个章节要搬：")
    for s, e, t in move_blocks:
        print(f"  {s+1:>5}-{e:<5} ({e-s:>4} 行) {t[:70]}")

    moved = "".join("".join(lines[s:e]) for s, e, _ in move_blocks)
    kept = "".join(l for l, m in zip(lines, keep_mask) if m)

    print(f"\n搬走 {len(moved)} 字符，留下 {len(kept)} 字符")
    if dry:
        return 0

    DST_DIR.mkdir(parents=True, exist_ok=True)
    (DST_DIR / "SKILL.md").write_text(HEADER + moved, encoding="utf-8")
    SRC.write_text(kept, encoding="utf-8")

    print(f"\n写出 {DST_DIR / 'SKILL.md'} ({(DST_DIR / 'SKILL.md').stat().st_size} 字节)")
    print(f"回写 {SRC} ({SRC.stat().st_size} 字节)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
