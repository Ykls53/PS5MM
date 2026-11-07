#!/usr/bin/env bash
# 收工清理：把探针相关补丁全部回退，恢复干净的 app/main.cpp
set -uo pipefail
S=/home/yk/PS5MM/scripts
for p in patch-exec-probe9.py patch-exec-probe8.py patch-exec-probe7.py patch-exec-probe6.py patch-exec-probe5.py patch-exec-probe4.py patch-print-argv.py patch-exec-probe3.py; do
    if [ -f "$S/$p" ]; then
        python3 "$S/$p" --revert >/dev/null 2>&1 && echo "reverted $p" || true
    fi
done
echo "---- 残留探针检查 ----"
grep -c 'probe_exec_self\|ps5mm-probe\|probe-exec\|ps5mm-argv' /home/yk/PS5MM/ps5/app/main.cpp
echo "---- main 签名 ----"
grep -n '^int main' /home/yk/PS5MM/ps5/app/main.cpp
