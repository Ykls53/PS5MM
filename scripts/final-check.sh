#!/usr/bin/env bash
set -uo pipefail
D=/mnt/d/deepseekDAIGirlfriend/_research/PS5MM/deliver-20261105
echo "==== zip contents ===="
python3 - "$D/PS5MM-PPSA99577-20261105.zip" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
print(f"{len(names)} entries")
for n in names[:14]:
    print("  ", n, z.getinfo(n).file_size)
eboot = [n for n in names if n.endswith("eboot.bin")]
if eboot:
    info = z.getinfo(eboot[0])
    print("eboot in zip:", info.file_size, "bytes")
PY
echo "==== host still alive ===="
curl -s -m 5 -o /dev/null -w 'ctrl=%{http_code}\n' http://127.0.0.1:8099/alive
curl -s -m 10 http://127.0.0.1:8002/health
echo
echo "==== final tree ===="
ls -l "$D"
