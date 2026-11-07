#!/usr/bin/env python3
"""PS5 SDK 没有 execl，但有 execv（libkernel.so 里定义了）。

这是个好消息：exec 系列确实支持，只是要用带 argv 数组的 execv。

    python3 patch-exec-probe5.py [--check|--revert]
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")

OLD = """    if (pid == 0) {
        ::execl(exe, exe, "--probe-child", static_cast<char *>(nullptr));
        std::printf("ps5mm-probe: child execl failed errno=%d\\n", errno);
        std::fflush(nullptr);
        ::_exit(127);
    }"""

NEW = """    if (pid == 0) {
        // PS5 SDK 没有 execl，只有 execv（argv 数组形式）
        char * child_argv[3];
        child_argv[0] = exe;
        child_argv[1] = const_cast<char *>("--probe-child");
        child_argv[2] = nullptr;
        ::execv(exe, child_argv);
        std::printf("ps5mm-probe: child execv failed errno=%d\\n", errno);
        std::fflush(nullptr);
        ::_exit(127);
    }"""


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = M.read_text(encoding="utf-8")
    if mode == "--check":
        print(f"old={src.count(OLD)} new={src.count(NEW)}")
        return 0
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
        print(f"anchor x{src.count(OLD)}; refusing", file=sys.stderr)
        return 2
    M.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched: execl -> execv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
