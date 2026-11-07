#!/usr/bin/env bash
set -uo pipefail
F=/home/yk/PS5MM/ps5/app/main.cpp
sed -n "/static int probe_exec_self/,/^}/p" "$F"
