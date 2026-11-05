#!/usr/bin/env python3
"""从源码里提取烘焙 CJK 字体要用的字符集。

为什么需要两套：
  * charset-ui.txt   —— 源码里出现过的界面字符（几百个）
  * charset-chat.txt —— 界面的字 + GB2312 全集（6763 汉字 + 符号）

聊天面板显示的是**模型生成的中文**，任意汉字都可能出现。只装界面那几百个字，
模型一开口就是一片 ????。这就是汉化第一版翻车的地方。

用法：
    python3 scripts/gen-charset.py <源码根> <输出目录>
产出：
    <输出目录>/charset-ui.txt
    <输出目录>/charset-chat.txt
"""
import sys
import pathlib

def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    root = pathlib.Path(sys.argv[1]).resolve()
    out_dir = pathlib.Path(sys.argv[2]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 源码里出现过的非 ASCII 字符
    ui = set()
    exts = {'.cpp', '.hpp', '.h', '.c'}
    skip = ('third_party', 'build', '.git', '.deps')
    files = 0
    for p in root.rglob('*'):
        if p.suffix not in exts or not p.is_file():
            continue
        if any(part in skip for part in p.parts):
            continue
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        files += 1
        ui.update(ch for ch in text if ord(ch) > 0x7f)

    # 界面里可能出现、但源码里暂时没有的标点
    ui.update('，。？！：；、（）「」『』《》〈〉—…％～·○●□△▽▲▶▼◀×÷°±※￥€℃')

    # 2. GB2312 全集（6763 汉字 + 682 符号）
    gb = set()
    for hi in range(0xA1, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                gb.add(bytes([hi, lo]).decode('gb2312'))
            except UnicodeDecodeError:
                pass

    ui_sorted = ''.join(sorted(ui))
    chat_sorted = ''.join(sorted(gb | ui))
    (out_dir / 'charset-ui.txt').write_text(ui_sorted, encoding='utf-8')
    (out_dir / 'charset-chat.txt').write_text(chat_sorted, encoding='utf-8')

    ui_cjk = sum(1 for c in ui if 0x4e00 <= ord(c) <= 0x9fff)
    chat_cjk = sum(1 for c in (gb | ui) if 0x4e00 <= ord(c) <= 0x9fff)
    print(f'扫描 {files} 个源文件')
    print(f'界面字集: {len(ui_sorted)} 字符（汉字 {ui_cjk}）-> {out_dir}/charset-ui.txt')
    print(f'聊天字集: {len(chat_sorted)} 字符（汉字 {chat_cjk}）-> {out_dir}/charset-chat.txt')
    return 0


if __name__ == '__main__':
    sys.exit(main())
