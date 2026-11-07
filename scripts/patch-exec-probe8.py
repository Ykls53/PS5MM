#!/usr/bin/env python3
"""删掉 main 开头残留的那份探针（保留 freopen 之后那份）。

上一版 patch-exec-probe7 的 OLD1 锚点没匹配上（字符串里有转义差异），
结果插了一份新的、旧的还在。这里用行号定位删除。

    python3 patch-exec-probe8.py [--check]
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")

START = "    // PS5 title 启动时拿不到命令行参数"
END = "    // /data first: the log, the settings and the models live there."


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = M.read_text(encoding="utf-8")
    # 找 main 之后第一份探针块（在 /data first 之前）
    i = src.find("int main(int argc, char ** argv) {")
    if i < 0:
        print("no main", file=sys.stderr)
        return 2
    j = src.find(START, i)
    k = src.find(END, j)
    if j < 0 or k < 0 or j > i + 200:
        print(f"first probe block not immediately after main (j={j}, k={k}, main={i})")
        print("=> 开头没有残留探针，无需删除")
        return 0
    if mode == "--check":
        print(f"would delete {k-j} chars")
        return 0
    M.write_text(src[:j] + src[k:], encoding="utf-8")
    print(f"deleted first probe block ({k-j} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
