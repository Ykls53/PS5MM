#!/usr/bin/env python3
"""probe_exec_self 重写：一次验完 fork、各候选路径的 execv。

上一版 readlink 失败就返回，fork 根本没测。这版：
  1. 先单独 fork 一个空子进程（只写标记文件，不 exec）—— 验 fork 能不能用
  2. 再对每个候选路径（/proc/self/exe、/data/homebrew/PPSA99577/eboot.bin、
     /system_ex/app/PPSA99577/eboot.bin）试 execv
  3. 全部结果写进 app.log

    python3 patch-exec-probe9.py [--check|--revert]
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")

OLD = """static int probe_exec_self(void) {
    char    exe[4096];
    ssize_t n = ::readlink("/proc/self/exe", exe, sizeof exe - 1);
    std::printf("ps5mm-probe: readlink(/proc/self/exe) = %ld", (long) n);
    if (n > 0) {
        exe[n] = 0;
        std::printf(" '%s'\\n", exe);
    } else {
        std::printf(" (errno %d)\\n", errno);
    }
    std::fflush(nullptr);
    if (n <= 0) {
        std::printf("ps5mm-probe: RESULT=no_self_path\\n");
        std::fflush(nullptr);
        return 10;
    }
    // PS5 SDK 没有 waitpid / WIFEXITED 那一套宏，所以用文件通信：
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
        // PS5 SDK 没有 execl，只有 execv（argv 数组形式）
        char * child_argv[3];
        child_argv[0] = exe;
        child_argv[1] = const_cast<char *>("--probe-child");
        child_argv[2] = nullptr;
        ::execv(exe, child_argv);
        std::printf("ps5mm-probe: child execv failed errno=%d\\n", errno);
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
    return 12;
}"""

NEW = """static int probe_exec_self(void) {
    const char * mark = "/data/PS5MM/probe-exec-ok.txt";

    // ---- 第 1 件事：fork 能不能用 ----
    (void) std::remove(mark);
    {
        const pid_t pid = ::fork();
        if (pid < 0) {
            std::printf("ps5mm-probe: RESULT=fork_failed errno=%d\\n", errno);
            std::fflush(nullptr);
            return 11;
        }
        if (pid == 0) {
            if (std::FILE * f = std::fopen(mark, "w")) {
                std::fprintf(f, "fork ok (no exec)\\n");
                std::fclose(f);
            }
            ::_exit(0);
        }
        // 等 1 秒看标记
        for (int i = 0; i < 10; ++i) {
            ::usleep(100 * 1000);
            if (std::FILE * f = std::fopen(mark, "r")) {
                std::fclose(f);
                std::printf("ps5mm-probe: fork=OK\\n");
                std::fflush(nullptr);
                break;
            }
        }
    }

    // ---- 第 2 件事：各候选路径的 execv ----
    const char * cands[] = {
        "/proc/self/exe",
        "/data/homebrew/PPSA99577/eboot.bin",
        "/system_ex/app/PPSA99577/eboot.bin",
        "/app0/eboot.bin",
    };
    for (const char * path : cands) {
        (void) std::remove(mark);
        char    exe[4096];
        ssize_t n = (std::strcmp(path, "/proc/self/exe") == 0)
                        ? ::readlink(path, exe, sizeof exe - 1) : -1;
        if (n > 0) {
            exe[n] = 0;
            path = exe;   // readlink 成功就用它
        }
        std::printf("ps5mm-probe: trying '%s'\\n", path);
        std::fflush(nullptr);

        const pid_t pid = ::fork();
        if (pid < 0) {
            std::printf("ps5mm-probe:   fork failed errno=%d\\n", errno);
            std::fflush(nullptr);
            continue;
        }
        if (pid == 0) {
            char * argv[3];
            char   pbuf[4096];
            std::strncpy(pbuf, path, sizeof pbuf - 1);
            pbuf[sizeof pbuf - 1] = 0;
            argv[0] = pbuf;
            argv[1] = const_cast<char *>("--probe-child");
            argv[2] = nullptr;
            ::execv(path, argv);
            std::printf("ps5mm-probe:   execv failed errno=%d\\n", errno);
            std::fflush(nullptr);
            ::_exit(127);
        }

        bool ok = false;
        for (int i = 0; i < 20; ++i) {
            ::usleep(100 * 1000);
            if (std::FILE * f = std::fopen(mark, "r")) {
                char buf[64] = { 0 };
                (void) std::fread(buf, 1, sizeof buf - 1, f);
                std::fclose(f);
                std::printf("ps5mm-probe:   RESULT=EXEC_OK (%s) path=%s\\n", buf, path);
                std::fflush(nullptr);
                ok = true;
                break;
            }
        }
        if (!ok) {
            std::printf("ps5mm-probe:   RESULT=EXEC_FAILED path=%s\\n", path);
            std::fflush(nullptr);
        }
    }
    std::printf("ps5mm-probe: RESULT=done\\n");
    std::fflush(nullptr);
    return 0;
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
    print("patched: probe fork + all paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
