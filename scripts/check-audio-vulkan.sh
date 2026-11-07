#!/usr/bin/env bash
# audio.cpp 到底有没有 Vulkan 后端？链接进 PS5 的是哪个构建？
set -uo pipefail

echo "==== 1. audio.cpp 有几种 backend ===="
grep -rn 'AUDIOCPP_BACKEND\|backend_name\|backends\[\]' /home/yk/ext/audio.cpp/src/framework/*.cpp 2>/dev/null | head -15
echo "--- ggml 后端注册表 ---"
ls /home/yk/ext/audio.cpp/src/framework/ 2>/dev/null | head -20

echo
echo "==== 2. PS5 用的 .deps/audio-acx 里有什么 ===="
ls -l /home/yk/PS5MM/.deps/audio-acx/ 2>/dev/null

echo
echo "==== 3. 里面有没有 Vulkan 符号 ===="
for f in /home/yk/PS5MM/.deps/audio-acx/*.a; do
    n=$(nm -g "$f" 2>/dev/null | grep -c 'ggml_backend_vk\|vk_init\|ggml_vk' || true)
    printf '  %-42s vulkan_symbols=%s\n' "$(basename $f)" "$n"
done

echo
echo "==== 4. PS5 构建时用的 CMake 参数 ===="
grep -n 'audio\|AUDIOCPP\|VULKAN\|vulkan' /home/yk/PS5MM/scripts/build-app.sh 2>/dev/null | head -20
