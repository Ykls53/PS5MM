#!/usr/bin/env bash
# ggml-vulkan says "No devices found" while ncnn finds llvmpipe. Try forcing the
# software ICD explicitly.
set -uo pipefail
cd /home/yk/ext/audio.cpp || exit 1
echo "==== plain ===="
timeout 60 build-vulkan/bin/audiocpp_cli --list-devices 2>&1 | head -3
echo "==== VK_ICD_FILENAMES=lvp ===="
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json timeout 60 build-vulkan/bin/audiocpp_cli --list-devices 2>&1 | head -5
echo "==== VK_DRIVER_FILES=lvp ===="
VK_DRIVER_FILES=/usr/share/vulkan/icd.d/lvp_icd.json timeout 60 build-vulkan/bin/audiocpp_cli --list-devices 2>&1 | head -5
echo "==== is libvulkan linked dynamically? ===="
ldd build-vulkan/bin/audiocpp_cli 2>/dev/null | grep -i vulkan || echo "(no libvulkan in ldd -> static loader)"
echo "==== does ggml-vulkan log more with GGML_VK_DEBUG? ===="
GGML_VK_VERBOSE=1 GGML_VK_DEBUG=1 timeout 60 build-vulkan/bin/audiocpp_cli --list-devices 2>&1 | head -8
