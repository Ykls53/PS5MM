#!/usr/bin/env python3
"""把探针块从 main 开头挪到 freopen 之后。

原因：探针在 open_data()/freopen 之前跑时，/data 还不可访问（触发文件读不到），
printf 也还没重定向到 app.log（什么都看不到）。

    python3 patch-exec-probe7.py [--check|--revert]
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")

BLOCK = """    // PS5 title 启动时拿不到命令行参数（测试 --probe-exec 走不通），
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
            std::printf("ps5mm-probe: child alive, exec worked\\n");
            std::fflush(nullptr);
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
    }
"""

# 1. 删掉 main 开头的探针块
OLD1 = """int main(int argc, char ** argv) {
""" + BLOCK + """    // /data first: the log, the settings and the models live there."""
NEW1 = """int main(int argc, char ** argv) {
    // /data first: the log, the settings and the models live there."""

# 2. 在 version printf 之前插回探针块
OLD2 = """    std::printf("ps5lm-app: version " PS5LM_VERSION "\\n");"""
NEW2 = BLOCK + """    std::printf("ps5lm-app: version " PS5LM_VERSION "\\n");"""

EDITS = [(OLD1, NEW1, "remove probe from main top"), (OLD2, NEW2, "insert probe after freopen")]


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = M.read_text(encoding="utf-8")
    if mode == "--check":
        for old, new, tag in EDITS:
            print(f"{'applied' if new in src else ('todo' if old in src else 'MISSING'):8s} {tag}")
        return 0
    if mode == "--revert":
        for old, new, tag in reversed(EDITS):
            if new in src:
                src = src.replace(new, old, 1)
        M.write_text(src, encoding="utf-8")
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
    M.write_text(src, encoding="utf-8")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
