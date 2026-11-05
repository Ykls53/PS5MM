#!/usr/bin/env bash
# Wrap the whole title folder (eboot + sce_sys + assets + payloads) into one zip,
# which is what "the app" actually is on the console.
set -uo pipefail
D=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/deliver-20261105
rm -f "$D/PS5MM-PPSA99577-20261105.zip"
python3 - "$D" <<'PY'
import os
import shutil
import sys
out = os.path.join(sys.argv[1], "PS5MM-PPSA99577-20261105")
made = shutil.make_archive(out, "zip", "/home/yk/PS5MM/build/app-ps5/title")
print("zip:", made, os.path.getsize(made), "bytes")
PY
ls -l "$D"
