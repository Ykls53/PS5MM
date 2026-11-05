#!/usr/bin/env python3
"""把 translations-zh.csv 里的英文界面文案替换成中文。

用法：
    python3 scripts/apply-translations.py <源码根> [词条表] [--dry-run]

规则：
  * 只替换**带双引号的完整字面量** —— `"Load"` 不会误伤 `"Loading"`
  * 同一文件内全部命中都替换（译文一致，不会出现同一个词两种译法）
  * 一条都没命中的列在最后，用来抓错字和漏项
  * 改完把原文件留一份 `<文件>.en.bak`（已在 .gitignore 里）

⚠ 这个脚本**只做字面量替换**。像 `wrap()` 断行、`read_file` 上限这类逻辑改动
   不在词条表里，那些是单独改的代码。
"""
import csv
import sys
import shutil
from pathlib import Path

SKIP_DIRS = {'third_party', 'build', '.git', '.deps', 'assets', 'node_modules'}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1]).resolve()
    table = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 and not sys.argv[2].startswith('-') \
        else Path(__file__).with_name('translations-zh.csv')
    dry = '--dry-run' in sys.argv

    if not table.exists():
        print(f'找不到词条表: {table}', file=sys.stderr)
        return 2

    rows = []
    with table.open(encoding='utf-8', newline='') as fh:
        for rec in csv.DictReader(fh):
            name = (rec.get('file') or '').strip()
            en = rec.get('en') or ''
            zh = rec.get('zh') or ''
            if name and en and zh:
                rows.append((name, en, zh))
    print(f'词条: {len(rows)}')

    by_file: dict[str, list[tuple[str, str]]] = {}
    for name, en, zh in rows:
        by_file.setdefault(name, []).append((en, zh))

    misses = []
    total = 0
    for name, pairs in by_file.items():
        target = None
        for cand in root.rglob(name):
            if any(part in SKIP_DIRS for part in cand.parts) or not cand.is_file():
                continue
            target = cand
            break
        if target is None:
            misses.append((name, '(文件没找到)'))
            continue
        text = target.read_text(encoding='utf-8')
        original = text
        replaced = 0
        for en, zh in pairs:
            needle, hay = '"' + en + '"', '"' + zh + '"'
            n = text.count(needle)
            if n == 0:
                misses.append((name, en))
                continue
            text = text.replace(needle, hay)
            replaced += n
            total += n
        if text != original and not dry:
            bak = target.with_suffix(target.suffix + '.en.bak')
            if not bak.exists():
                shutil.copy2(target, bak)
            target.write_text(text, encoding='utf-8')
        print(f'{name}: 替换 {replaced} 处{"（dry-run）" if dry else ""}')

    print(f'\n合计替换 {total} 处')
    if misses:
        print(f'\n未命中 {len(misses)} 条:')
        for name, en in misses:
            print(f'  [{name}] {en}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
