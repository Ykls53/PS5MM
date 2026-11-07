#!/usr/bin/env python3
"""在 PS5 上验 fork+exec 自身（第 1 步）。

前一版失败原因：main 的签名是 `int main(int, char **)`（参数无名），
锚点写成带名字的反而匹配不上。这一版直接用真实签名做锚点，
并把签名改成带名字的，这样函数体里才能用 argc/argv。

    python3 patch-exec-probe3.py [--check|--revert]
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")

OLD = """int main(int, char **) {
    // /data first: the log, the settings and the models live there."""

NEW = """// ---- exec 自检验证（带 --probe-exec 参数时才跑）---------------------------
// 语音每句退化（PC 实测：第一句 3.8s，之后 40~90s，重启进程立刻恢复）。
// 解法是每句换新进程，PS5 只有一个 eboot.bin，所以要验能不能 exec 自己。
static int probe_exec_self(void) {
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
    return 13;
}

int main(int argc, char ** argv) {
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
    // /data first: the log, the settings and the models live there."""


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
    print("patched: exec probe at main's first line")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
