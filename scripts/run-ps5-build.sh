#!/usr/bin/env bash
set -uo pipefail
cd /home/yk/PS5MM
export PS5_OPENGL_SDK=/home/yk/PS5SD/.deps/ps5-opengl-sdk
export PS5LM_PREBUILT_UI=OFF
export CMAKE_BUILD_PARALLEL_LEVEL="${BUILD_JOBS:-8}"
timeout 3600 bash scripts/build-app.sh > /tmp/ps5-build.log 2>&1
rc=$?
echo "EXIT=$rc"
grep -nE 'error:|ERROR|undefined reference' /tmp/ps5-build.log | head -25
echo "---- tail ----"
tail -14 /tmp/ps5-build.log
exit $rc
