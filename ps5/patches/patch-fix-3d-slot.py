#!/usr/bin/env python3
"""修 3D 槽位算法：加 video_slot 占掉 4 号之后，只剩 5 号一个空位，
原来的「taken==1 才取」逻辑永远取不到，3D 引擎根本没启动。

改成：找第一个没被 text/picture/speech/video 占用的槽位。
"""
import sys
from pathlib import Path

MAIN = Path("/home/yk/PS5MM/ps5/app/main.cpp")

OLD = """            int slot3d = 0;
            int taken  = 0;
            for (int s = 1; s <= 5; ++s) {
                if (s == boot.text_slot || s == boot.picture_slot || s == boot.speech_slot ||
                    s == boot.video_slot) {
                    continue;
                }
                // 第一个空闲给 audio，第二个给 3D
                if (taken == 1) {
                    slot3d = s;
                    break;
                }
                taken++;
            }"""

NEW = """            // 3D 取第一个没被前面四个引擎占用的槽位。
            // （原来写的是「第二个空闲」，那是给 audio 留位的年代；audio 删掉之后
            //   只剩一个空位，那个算法永远取不到值，3D 压根没启动。）
            int slot3d = 0;
            for (int s = 1; s <= 5; ++s) {
                if (s == boot.text_slot || s == boot.picture_slot || s == boot.speech_slot ||
                    s == boot.video_slot) {
                    continue;
                }
                slot3d = s;
                break;
            }"""

OLD2 = """            int slot3d = 0;
            int taken  = 0;
            for (int s = 1; s <= 5; ++s) {
                if (s == st.text_slot || s == st.picture_slot || s == st.speech_slot) {
                    continue;
                }
                if (taken == 1) {
                    slot3d = s;
                    break;
                }
                taken++;
            }"""

NEW2 = """            int slot3d = 0;
            for (int s = 1; s <= 5; ++s) {
                if (s == st.text_slot || s == st.picture_slot || s == st.speech_slot ||
                    s == st.video_slot) {
                    continue;
                }
                slot3d = s;
                break;
            }"""

EDITS = [(OLD, NEW, "3D slot (startup)"), (OLD2, NEW2, "3D slot (dashboard)")]


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = MAIN.read_text(encoding="utf-8")
    if mode == "--check":
        for old, new, tag in EDITS:
            print(f"{'applied' if new in src else ('todo' if old in src else 'MISSING'):8s} {tag}")
        return 0
    if mode == "--revert":
        for old, new, tag in reversed(EDITS):
            if new in src:
                src = src.replace(new, old, 1)
        MAIN.write_text(src, encoding="utf-8")
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
    MAIN.write_text(src, encoding="utf-8")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
