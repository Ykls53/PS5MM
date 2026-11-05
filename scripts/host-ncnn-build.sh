#!/usr/bin/env bash
# Builds ncnn for the PC with Vulkan enabled -- required, not optional: rife.h
# names ncnn::VulkanDevice and ncnn::Pipeline, so a CPU-only ncnn cannot even
# compile the RIFE sources. Runtime still runs the CPU path (gpuid = -1).
set -uo pipefail
SRC=/home/yk/ext/ncnn-rife
OUT=$SRC/build-hostvk
LOG=/tmp/ncnn-host-build.log

echo "==== prereqs ===="
ls /tmp/rife-shd 2>/dev/null | head -5
find /usr/lib/x86_64-linux-gnu/cmake /usr/lib/cmake -maxdepth 2 -name 'glslang-config.cmake' 2>/dev/null | head -3

GLSLANG_DIR=$(find /usr/lib/x86_64-linux-gnu/cmake /usr/lib/cmake -maxdepth 2 -name 'glslang-config.cmake' 2>/dev/null | head -1)
GLSLANG_DIR=$(dirname "${GLSLANG_DIR:-/usr/lib/x86_64-linux-gnu/cmake/glslang}")
echo "glslang_DIR=$GLSLANG_DIR"

if [ ! -f "$OUT/build.ninja" ]; then
    cmake -S "$SRC" -B "$OUT" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DNCNN_VULKAN=ON -DNCNN_SYSTEM_GLSLANG=ON -Dglslang_DIR="$GLSLANG_DIR" \
        -DNCNN_INSTALL_SDK=OFF -DNCNN_BUILD_TOOLS=OFF -DNCNN_BUILD_EXAMPLES=OFF \
        -DNCNN_BUILD_BENCHMARK=OFF -DNCNN_BUILD_TESTS=OFF -DNCNN_BUILD_PYTHON=OFF \
        -DNCNN_BUILD_C_API=OFF -DNCNN_OPENMP=ON \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 > "$LOG" 2>&1 || { echo "CONFIGURE FAILED"; tail -25 "$LOG"; exit 1; }
    echo "configured"
fi

cmake --build "$OUT" -j "$(nproc)" >> "$LOG" 2>&1 || { echo "BUILD FAILED"; grep -nE 'error:' "$LOG" | head -20; tail -15 "$LOG"; exit 1; }
echo "BUILD OK"
ls -l "$OUT/src/libncnn.a" 2>/dev/null || echo "(no libncnn.a yet)"
