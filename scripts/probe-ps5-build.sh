#!/usr/bin/env bash
# Are the console cross-build inputs still on disk before we spend 20 minutes?
set -uo pipefail
R=/home/yk/PS5MM
echo "==== .deps ===="
ls -1 "$R/.deps" 2>/dev/null
echo "==== PS5_Vulkan ===="
ls -d "$R/.deps/src/PS5_Vulkan" 2>/dev/null || ls -d /home/yk/PS5SD/.deps/src/PS5_Vulkan 2>/dev/null
echo "==== radv / sdk / libc ===="
ls -l "$R/.deps/src/PS5_Vulkan/.deps/native/radv-release/lib/libvulkan_radeon.ps5.a" 2>/dev/null
ls -l "$R/.deps/src/PS5_Vulkan/.deps/native/ps5-payload-sdk/bin/prospero-lld" 2>/dev/null
ls -l "$R/.deps/src/PS5_Vulkan/runtime/libc.prx" 2>/dev/null
echo "==== ps5-opengl ===="
ls -d /home/yk/PS5SD/.deps/ps5-opengl-sdk 2>/dev/null && ls /home/yk/PS5SD/.deps/ps5-opengl-sdk/lib/libPS5OpenGL.a 2>/dev/null
echo "==== audio/trellis/rife prefixed libs ===="
ls -d "$R/.deps/audio-acx" "$R/.deps/trellis-trx" 2>/dev/null
ls -1 "$R/.deps/audio-acx" 2>/dev/null | head -5
echo "==== ext deps ===="
for d in /home/yk/ext/ffmpeg /home/yk/ext/ncnn-rife/build-ps5vk /home/yk/ext/rife-ncnn /tmp/rife-shd /home/yk/ext/trellis.cpp /home/yk/ext/glslang/prefix; do
    [ -e "$d" ] && echo "PRESENT $d" || echo "MISSING $d"
done
