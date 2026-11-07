#!/usr/bin/env python3
"""PS5 title 启动时拿不到命令行参数，所以探针不能靠 --probe-exec 触发。

改成：看一个「触发文件」。往 /data/PS5MM/probe-exec 扔个文件，
主循环（或启动时）看到就跑探针。这样不用重新部署就能触发。

但探针在 main 最开头，那时还没读 settings。所以改成：
  * 启动时检查 /data/PS5MM/probe-exec-request 存在 -> 跑探针 -> 写结果 -> 正常继续
  * 结果写 /data/PS5MM/probe-exec-result.txt

    python3 patch-exec-probe6.py [--check|--revert]
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")

OLD = """int main(int argc, char ** argv) {
    // 先看清 argv 到底是什么（怀疑 PS5 title 启动时 argc=1 且 argv[0] 为 null）
    std::printf("ps5mm-argv: argc=%d\\n", argc);
    for (int i = 0; i < argc && i < 8; ++i) {
        std::printf("ps5mm-argv:   [%d] = %s\\n", i, argv[i] != nullptr ? argv[i] : "(null)");
    }
    std::fflush(nullptr);
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--probe-child") == 0) {
            if (std::FILE * f = std::fopen("/data/PS5MM/probe-exec-ok.txt", "w")) {
                std::fprintf(f, "child alive, exec worked\\n");
                std::fclose(f);
            }
            std::printf("ps5mm-probe: child alive, exec worked\\n");
            std::fflush(nullptr);
            ::_exit(0);
        }
        if (std::strcmp(argv[i], "--probe-exec") == 0) {
            ::_exit(probe_exec_self());
        }
    }"""

NEW = """int main(int argc, char ** argv) {
    // PS5 title 启动时拿不到命令行参数（测试 --probe-exec 走不通），
    // 所以用「触发文件」：往 /data/PS5MM/probe-exec-request 扔个文件，
    // 下一次启动就会跑探针，结果写 probe-exec-result.txt。
    {
        // 子进程被 exec 进来时，argv[1] 会是 --probe-child（这个能拿到，
        // 因为是我们自己 execv 时传的）
        bool child = false;
        for (int i = 1; i < argc; ++i) {
            if (argv[i] != nullptr && std::strcmp(argv[i], "--probe-child") == 0) {
                child = true;
            }
        }
        if (child) {
            if (std::FILE * f = std::fopen("/data/PS5MM/probe-exec-ok.txt", "w")) {
                std::fprintf(f, "child alive, exec worked\\n");
                std::fclose(f);
            }
            ::_exit(0);
        }
        // 触发文件：存在就跑探针
        if (std::FILE * rf = std::fopen("/data/PS5MM/probe-exec-request", "r")) {
            std::fclose(rf);
            const int rc = probe_exec_self();
            if (std::FILE * of = std::fopen("/data/PS5MM/probe-exec-result.txt", "w")) {
                std::fprintf(of, "probe rc=%d\\n", rc);
                std::fclose(of);
            }
            (void) std::remove("/data/PS5MM/probe-exec-request");
        }
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
    print("patched: trigger file instead of argv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
