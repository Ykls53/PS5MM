#!/usr/bin/env bash
# Prove the console build actually recompiled the patched sources (mtime order).
set -uo pipefail
echo "==== source vs object mtimes ===="
for pair in \
    "/home/yk/ext/rife-ncnn/src/rife.cpp /home/yk/PS5MM/build/app-ps5/obj/rife.o" \
    "/home/yk/ext/rife-ncnn/src/rife.cpp /home/yk/PS5MM/build/app-ps5/obj/rife_warp.o" \
    "/home/yk/PS5MM/ps5/app/dashboard.cpp /home/yk/PS5MM/build/app-ps5/obj/dashboard.o" \
    "/home/yk/PS5MM/ps5/app/sd_server.cpp /home/yk/PS5MM/build/app-ps5/obj/sd_server.o" \
    "/home/yk/PS5MM/ps5/app/settings.cpp /home/yk/PS5MM/build/app-ps5/obj/settings.o" \
    "/home/yk/PS5MM/ps5/app/tts_server.cpp /home/yk/PS5MM/build/app-ps5/obj/tts_server.o"; do
    set -- $pair
    src=$1; obj=$2
    if [ -f "$src" ] && [ -f "$obj" ]; then
        st=$(stat -c %Y "$src"); ot=$(stat -c %Y "$obj")
        if [ "$ot" -ge "$st" ]; then verdict="OK  (object newer)"; else verdict="STALE OBJECT"; fi
        printf '%-60s %s\n' "$(basename "$src") -> $(basename "$obj")" "$verdict"
    else
        printf '%-60s %s\n' "$src -> $obj" "MISSING"
    fi
done
echo "==== eboot ===="
stat -c '%y %s %n' /home/yk/PS5MM/build/app-ps5/title/PPSA99577/eboot.bin
