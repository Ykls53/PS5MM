#!/usr/bin/env bash
# Where does stable-diffusion.cpp pick its backend, and what does auto_fit=false
# actually force? This decides whether the console's picture engine runs on the
# GPU or silently crawls on the CPU.
set -uo pipefail
SD=/home/yk/PS5MM/third_party/stable-diffusion.cpp
echo "==== files ===="
ls "$SD/src/core" 2>/dev/null | head -20
echo "==== auto_fit / backend selection ===="
grep -rnE 'auto_fit|ggml_backend_init_best|ggml_backend_dev_by_type|params\.backend|SD_BACKEND' "$SD/src" --include=*.cpp --include=*.hpp | head -30
echo "==== backend_fit.cpp around the PS5 branch ===="
sed -n '150,240p' "$SD/src/core/backend_fit.cpp" 2>/dev/null
