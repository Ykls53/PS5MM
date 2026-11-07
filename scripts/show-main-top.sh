#!/usr/bin/env bash
set -uo pipefail
F=/home/yk/PS5MM/ps5/app/main.cpp
N=$(grep -n 'int main' "$F" | head -1 | cut -d: -f1)
echo "main at line $N"
sed -n "${N},$((N+50))p" "$F"
