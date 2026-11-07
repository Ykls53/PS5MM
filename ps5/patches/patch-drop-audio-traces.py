#!/usr/bin/env python3
"""拔掉最后两处 audio.cpp 的痕迹：extern 声明 + 那句 abi 打印。

那句 `std::printf("ps5mm-app: audio abi %d\n", audiocpp_abi_version())` 是以前
用来「证明 C API 链进来了」的探针；引擎删了，它就没意义了。
"""
import sys
from pathlib import Path

MAIN = Path("/home/yk/PS5MM/ps5/app/main.cpp")

OLD = """// audio.cpp's C API (include/audiocpp.h upstream). Declared here rather than
// including the header: the engine's other declarations would drag its own
// copies of ggml types into this translation unit.
extern "C" int audiocpp_abi_version(void);

"""

NEW = ""

OLD2 = """    // The audio engine (audio.cpp, ACX_ prefixed): one call proves the C API is
    // reachable from this binary. Static libraries only pull their objects in
    // when something references them, so without this the whole engine would be
    // silently dropped at link time.
    std::printf("ps5mm-app: audio abi %d\\n", audiocpp_abi_version());
"""

NEW2 = "    // audio.cpp 引擎已移除（2026-11-05）：8004 那个槽位改给视频。\n"


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = MAIN.read_text(encoding="utf-8")
    if mode == "--revert":
        if NEW2 in src:
            src = src.replace(NEW2, OLD2, 1)
        if NEW == "" and OLD not in src:
            src = src.replace(
                '#include "trellis_server.hpp"\n\n',
                '#include "trellis_server.hpp"\n\n' + OLD, 1)
        MAIN.write_text(src, encoding="utf-8")
        print("reverted")
        return 0
    failed = False
    for old, new, tag in ((OLD, NEW, "extern decl"), (OLD2, NEW2, "abi print")):
        if old not in src:
            print(f"skip     {tag}（已经不在）")
            continue
        if src.count(old) != 1:
            print(f"FAILED   {tag}: anchor x{src.count(old)}", file=sys.stderr)
            failed = True
            continue
        src = src.replace(old, new, 1)
        print(f"patched  {tag}")
    MAIN.write_text(src, encoding="utf-8")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
