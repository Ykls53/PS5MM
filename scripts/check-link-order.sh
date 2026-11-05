#!/usr/bin/env bash
set -uo pipefail
O=/home/yk/PS5MM/build/app-ps5/obj
E=/home/yk/PS5MM/build/app-ps5/title/PPSA99577/eboot.bin
echo "==== object times ===="
stat -c '%y  %n' "$O/rife.o" "$O/rife_warp.o" "$O/interp_server.o" "$O/dashboard.o" "$O/sd_server.o" 2>/dev/null
echo "==== eboot time ===="
stat -c '%y  %n' "$E"
echo "==== verdict ===="
python3 - "$O/rife.o" "$O/dashboard.o" "$E" <<'PY'
import os, sys
rife, dash, eboot = (os.path.getmtime(p) for p in sys.argv[1:4])
print(f"rife.o  {'BEFORE' if rife <= eboot else 'AFTER'} eboot")
print(f"dash.o  {'BEFORE' if dash <= eboot else 'AFTER'} eboot")
PY
