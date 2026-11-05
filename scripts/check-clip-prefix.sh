#!/usr/bin/env bash
set -uo pipefail
SD=/home/yk/PS5MM/third_party/stable-diffusion.cpp
echo "==== get_sd_version tensor names ===="
grep -rn "token_embedding.weight" "$SD/src" | head -20
echo "==== git status of the sd tree (is the patch still in?) ===="
git -C "$SD" status --porcelain 2>/dev/null | head -10
echo "==== when was build-x86's lib built vs the source ===="
stat -c '%y %n' "$SD/libstable-diffusion.a" 2>/dev/null || stat -c '%y %n' "$SD/build-x86/libstable-diffusion.a"
stat -c '%y %n' "$SD/src/model_loader.cpp"
