#!/usr/bin/env python3
"""PS5 SDK 没有 waitpid / WIFEXITED / WEXITSTATUS / WIFSIGNALED / WTERMSIG。

这本身就是个结论：PS5 原生 title 的进程管理接口不全。
不能等子进程，只能用别的办法判断 exec 成没成：
  * 子进程往一个文件里写标记（最直接）
  * 父进程 sleep 一下再读那个文件

改成这种「用文件通信」的写法，两个平台都能跑。

    python3 patch-exec-probe4.py [--check|--revert]
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")

OLD = """    const pid_t pid = ::fork();
    if (pid < 0) {
        std::printf("ps5mm-probe: RESULT=fork_failed errno=%d\\n", errno);
        std::fflush(nullptr);
        return 11;
    }
    if (pid == 0) {
        ::execl(exe, exe, "--probe-child", static_cast<char *>(nullptr));
        std::printf("ps5mm-probe: child execl failed errno=%d\\n", errno);
        std::fflush(nullptr);
        ::_exit(127);
    }
    int status = 0;
    (void) ::waitpid(pid, &status, 0);
    if (WIFEXITED(status)) {
        const int code = WEXITSTATUS(status);
        std::printf("ps5mm-probe: child exit=%d RESULT=%s\\n", code, code == 0 ? "EXEC_OK" : "EXEC_FAILED");
        std::fflush(nullptr);
        return code == 0 ? 0 : 12;
    }
    std::printf("ps5mm-probe: child signal=%d RESULT=EXEC_CRASHED\\n",
                WIFSIGNALED(status) ? WTERMSIG(status) : 0);
    std::fflush(nullptr);
    return 13;"""

NEW = """    // PS5 SDK 没有 waitpid / WIFEXITED 那一套宏，所以用文件通信：
    // 子进程 exec 成功后写一个标记文件，父进程 sleep 一会儿读它。
    const char * mark = "/data/PS5MM/probe-exec-ok.txt";
    (void) std::remove(mark);

    const pid_t pid = ::fork();
    if (pid < 0) {
        std::printf("ps5mm-probe: RESULT=fork_failed errno=%d\\n", errno);
        std::fflush(nullptr);
        return 11;
    }
    if (pid == 0) {
        ::execl(exe, exe, "--probe-child", static_cast<char *>(nullptr));
        std::printf("ps5mm-probe: child execl failed errno=%d\\n", errno);
        std::fflush(nullptr);
        ::_exit(127);
    }

    // 等 2 秒，看子进程有没有写标记
    for (int i = 0; i < 20; ++i) {
        ::usleep(100 * 1000);
        if (std::FILE * f = std::fopen(mark, "r")) {
            char buf[64] = { 0 };
            (void) std::fread(buf, 1, sizeof buf - 1, f);
            std::fclose(f);
            std::printf("ps5mm-probe: RESULT=EXEC_OK (marker: %s)\\n", buf);
            std::fflush(nullptr);
            return 0;
        }
    }
    std::printf("ps5mm-probe: RESULT=EXEC_FAILED (no marker after 2s)\\n");
    std::fflush(nullptr);
    return 12;"""

OLD2 = """        if (std::strcmp(argv[i], "--probe-child") == 0) {
            std::printf("ps5mm-probe: child alive, exec worked\\n");
            std::fflush(nullptr);
            ::_exit(0);
        }"""

NEW2 = """        if (std::strcmp(argv[i], "--probe-child") == 0) {
            if (std::FILE * f = std::fopen("/data/PS5MM/probe-exec-ok.txt", "w")) {
                std::fprintf(f, "child alive, exec worked\\n");
                std::fclose(f);
            }
            std::printf("ps5mm-probe: child alive, exec worked\\n");
            std::fflush(nullptr);
            ::_exit(0);
        }"""

EDITS = [(OLD, NEW, "probe: file marker instead of waitpid"),
         (OLD2, NEW2, "child: write marker file")]


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
