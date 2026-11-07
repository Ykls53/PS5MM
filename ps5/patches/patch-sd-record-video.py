#!/usr/bin/env python3
"""ensure_ctx 一进去就把 want_video 记下来，界面才有得问。"""
import sys
from pathlib import Path

S = Path("/home/yk/PS5MM/ps5/app/sd_server.cpp")

OLD = """bool ensure_ctx(bool want_video, std::string & err) {
    const SdModels & m = g_e.set_for(want_video);"""

NEW = """bool ensure_ctx(bool want_video, std::string & err) {
    g_want_video.store(want_video);   // 界面靠它分辨「谁在忙」
    const SdModels & m = g_e.set_for(want_video);"""


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = S.read_text(encoding="utf-8")
    if mode == "--revert":
        if NEW in src:
            S.write_text(src.replace(NEW, OLD, 1), encoding="utf-8")
            print("reverted")
        else:
            print("nothing to revert")
        return 0
    if NEW in src:
        print("already applied")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor x{src.count(OLD)}")
    S.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched: ensure_ctx records want_video")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
