#!/usr/bin/env python3
"""把探针挪到 main() 真·第一行，并且修掉参数无名的坑。

上一版的问题：
  main 的签名是 `int main(int, char **)`（参数没有名字），
  我的补丁把签名改成了带名字的，但插入位置在那之后又包了一层作用域，
  导致 --probe-exec 分支没触发、程序继续跑到引擎初始化、最后段错误。

这一版：
  1. 直接把签名改成 `int main(int argc, char ** argv)`
  2. 探针调用放在函数体第一行（没有任何前置初始化）
  3. 探针自己处理 --probe-exec / --probe-child，不依赖外面的作用域

    python3 patch-exec-probe2.py [--check|--revert]
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")

OLD = """int main(int argc, char ** argv) {
    {
        const int probe = probe_exec_self(argc, argv);
        if (probe >= 0) {
            if (probe == 0) {
                ::_exit(0);   // 探针跑完就退，不启动任何引擎
            }
        }
    }
    // 子进程被 exec 进来时带 --probe-child：说明 exec 成功，立刻以 0 退出
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--probe-child") == 0) {
            std::printf("ps5mm-probe: child is alive, exec worked\\n");
            std::fflush(nullptr);
            ::_exit(0);
        }
    }
"""

NEW = """int main(int argc, char ** argv) {
    // 探针放第一行：任何初始化之前。
    //  --probe-exec  : 量 readlink + fork + exec 自身
    //  --probe-child : exec 进来的子进程，打印一行就退
    if (argc > 1) {
        for (int i = 1; i < argc; ++i) {
            if (std::strcmp(argv[i], "--probe-child") == 0) {
                std::printf("ps5mm-probe: child alive, exec worked\\n");
                std::fflush(nullptr);
                ::_exit(0);
            }
            if (std::strcmp(argv[i], "--probe-exec") == 0) {
                ::_exit(probe_exec_self());
            }
        }
    }
"""


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
    print("patched: probe at first line of main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
