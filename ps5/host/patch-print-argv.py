#!/usr/bin/env python3
"""别猜了：把 main 收到的 argv 全打出来。

怀疑：这个 eboot 的 main 拿到的 argc/argv 是空的（PS5 title 启动方式决定的），
或者 host 版有别的入口包装。

打完之后退出，不进引擎。
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")

OLD = """int main(int argc, char ** argv) {
    for (int i = 1; i < argc; ++i) {"""

NEW = """int main(int argc, char ** argv) {
    // 先看清 argv 到底是什么（怀疑 PS5 title 启动时 argc=1 且 argv[0] 为 null）
    std::printf("ps5mm-argv: argc=%d\\n", argc);
    for (int i = 0; i < argc && i < 8; ++i) {
        std::printf("ps5mm-argv:   [%d] = %s\\n", i, argv[i] != nullptr ? argv[i] : "(null)");
    }
    std::fflush(nullptr);
    for (int i = 1; i < argc; ++i) {"""


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = M.read_text(encoding="utf-8")
    if mode == "--revert":
        if NEW in src:
            M.write_text(src.replace(NEW, OLD, 1), encoding="utf-8")
            print("reverted")
        else:
            print("nothing to revert")
        return 0
    if NEW in src:
        print("already applied")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor x{src.count(OLD)}")
    M.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched: print argv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
