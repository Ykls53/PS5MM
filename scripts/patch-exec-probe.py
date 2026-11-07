#!/usr/bin/env python3
"""加一个 fork+exec 自身的探针（只跑一次，结果写 app.log）。

为什么需要：语音每句都退化（第一句 3.8s，之后 40~90s，重启进程立刻恢复）。
唯一确定有效的解法是「每句换一个新进程」，但 PS5 上只有一个 eboot.bin，
不能用 PC 那种「exec 兄弟二进制」的做法。

要先确认两件事：
  1. /proc/self/exe 在 PS5 上能不能读
  2. fork + exec 自己（同一个 eboot.bin）会不会被签名机制拦

探针放在 main() 很早的位置，只在 argv 里有 --probe-exec 时跑，然后 _exit(0)。
正常启动完全不受影响。

    python3 patch-exec-probe.py [--check|--revert]
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")

OLD = """int main(int, char **) {"""

NEW = """// ---- fork+exec 自检探针（只在 argv 带 --probe-exec 时跑）-----------------
// 语音每句都会退化（PC 实测：第一句 3.8s，之后 40~90s，重启进程立刻恢复）。
// 解法是每句换新进程，但 PS5 只有一个 eboot.bin，得确认能不能 exec 自己。
static int probe_exec_self(int argc, char ** argv) {
    bool probe = false;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--probe-exec") == 0) {
            probe = true;
        }
    }
    if (!probe) {
        return -1;   // 不是探针模式，正常往下走
    }
    std::printf("ps5mm-probe: ===== fork+exec self probe =====\\n");

    char    exe[4096];
    ssize_t n = ::readlink("/proc/self/exe", exe, sizeof exe - 1);
    std::printf("ps5mm-probe: readlink(/proc/self/exe) = %ld ", (long) n);
    if (n > 0) {
        exe[n] = 0;
        std::printf("'%s'\\n", exe);
    } else {
        std::printf("(failed, errno %d)\\n", errno);
    }
    std::fflush(nullptr);

    if (n <= 0) {
        std::printf("ps5mm-probe: RESULT=no_self_path  -> exec 自身不可行\\n");
        std::fflush(nullptr);
        return 0;
    }

    const pid_t pid = ::fork();
    if (pid < 0) {
        std::printf("ps5mm-probe: RESULT=fork_failed (errno %d)\\n", errno);
        std::fflush(nullptr);
        return 0;
    }
    if (pid == 0) {
        // 子进程：exec 自己，带一个标记参数避免递归
        ::execl(exe, "eboot.bin", "--probe-child", static_cast<char *>(nullptr));
        std::printf("ps5mm-probe: child execl failed, errno %d\\n", errno);
        std::fflush(nullptr);
        ::_exit(127);
    }

    int status = 0;
    (void) ::waitpid(pid, &status, 0);
    if (WIFEXITED(status)) {
        const int code = WEXITSTATUS(status);
        std::printf("ps5mm-probe: child exited %d -> RESULT=%s\\n", code,
                    code == 0 ? "exec_ok" : "exec_failed");
    } else {
        std::printf("ps5mm-probe: child killed by signal %d -> RESULT=exec_crashed\\n",
                    WIFSIGNALED(status) ? WTERMSIG(status) : 0);
    }
    std::fflush(nullptr);
    return 0;
}

int main(int argc, char ** argv) {
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
    print("patched: exec self probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
