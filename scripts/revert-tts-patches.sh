#!/usr/bin/env bash
# 回退 mctx 重建补丁（它让第二次开始直接 500）
set -uo pipefail
python3 /home/yk/PS5MM/scripts/patch-tts-rebuild-mctx.py --revert 2>&1
python3 /home/yk/PS5MM/scripts/patch-tts-rebuild-ctx.py --revert 2>&1
python3 /home/yk/PS5MM/scripts/patch-tts-seq-rm.py --revert 2>&1
echo "---- 回退后检查 ----"
grep -n 'memory_clear\|synchronize\|seq_rm\|rebuild' /home/yk/PS5MM/ps5/app/tts_server.cpp | head -10
echo "---- 重建 ----"
bash /home/yk/PS5MM/scripts/run-build.sh 2>&1 | tail -3
