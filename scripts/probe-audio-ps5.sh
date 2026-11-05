#!/usr/bin/env bash
# Why did the console's audio engine answer "no registered model loader can load"?
# Look at how its C API was configured.
set -uo pipefail
cd /home/yk/PS5MM/scripts || exit 1
echo "==== audio build configs present ===="
ls -1 build-audio*.sh cross-configure-audio*.sh prefix-audio.sh 2>/dev/null
echo "==== cmake flags mentioning ESPEAK / MODEL_SET / C_API ===="
grep -nE 'AUDIOCPP_(STATIC_ESPEAK|MODEL_SET|MODELS|BUILD_C_API|USE_SYSTEM_OPENSSL)|espeak' build-audio*.sh cross-configure-audio*.sh prefix-audio.sh 2>/dev/null | head -25
echo "==== the acx archives ===="
ls -l /home/yk/PS5MM/.deps/audio-acx
echo "==== does the console lib reference espeak? ===="
NM=/home/yk/PS5MM/.deps/src/PS5_Vulkan/.deps/native/ps5-payload-sdk/bin/llvm-nm
if [ -x "$NM" ]; then
    "$NM" -u /home/yk/PS5MM/.deps/audio-acx/libengine_runtime.a 2>/dev/null | grep -iE 'espeak|phonem' | head -10 || echo "(no espeak undefined symbols)"
else
    echo "(no llvm-nm)"
fi
