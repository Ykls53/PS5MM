// 极简探针：只测 readlink(/proc/self/exe) + fork + exec 自身。
// 不链任何引擎，不读 settings，不碰显示。单独编单独跑。
#include <cstdio>
#include <cstring>
#include <cerrno>
#include <unistd.h>
#include <sys/wait.h>

int main(int argc, char ** argv) {
    // 子进程被 exec 进来时带这个参数
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--child") == 0) {
            std::printf("CHILD-PROBE: alive\n");
            std::fflush(stdout);
            return 0;
        }
    }

    std::printf("=== exec self probe ===\n");
    char    exe[4096];
    ssize_t n = ::readlink("/proc/self/exe", exe, sizeof exe - 1);
    std::printf("readlink -> %ld", (long) n);
    if (n > 0) {
        exe[n] = 0;
        std::printf(" '%s'\n", exe);
    } else {
        std::printf(" errno=%d\n", errno);
        return 1;
    }
    std::fflush(stdout);

    const pid_t pid = ::fork();
    if (pid < 0) {
        std::printf("fork failed: errno=%d\n", errno);
        return 1;
    }
    if (pid == 0) {
        ::execl(exe, exe, "--child", static_cast<char *>(nullptr));
        std::printf("CHILD: execl failed errno=%d\n", errno);
        std::fflush(stdout);
        ::_exit(127);
    }

    int status = 0;
    (void) ::waitpid(pid, &status, 0);
    if (WIFEXITED(status)) {
        const int code = WEXITSTATUS(status);
        std::printf("child exit=%d  RESULT=%s\n", code, code == 0 ? "EXEC_OK" : "EXEC_FAILED");
    } else {
        std::printf("child signal=%d  RESULT=EXEC_CRASHED\n", WIFSIGNALED(status) ? WTERMSIG(status) : 0);
    }
    return 0;
}
