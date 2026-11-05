#!/usr/bin/env bash
# 先把现场存进 git —— 从此每次改动都能 diff、能 revert
set -uo pipefail
cd /home/yk/PS5MM || exit 1
if [ -d .git ]; then
    echo "already a repo:"; git log --oneline -3
    git status --porcelain | head -20
    exit 0
fi
cat > .gitignore <<'EOF'
build/
.deps/
third_party/llama.cpp/
third_party/stable-diffusion.cpp/
*.o
*.a
*.so
*.bin
*.gguf
*.safetensors
EOF
git init -q
git config user.email "local@ps5mm"
git config user.name "PS5MM"
git add -A 2>/dev/null
git commit -q -m "state as of 2026-11-05 evening: source does NOT match the working eboot (338,837,736)" 2>&1 | tail -3
git tag unknown-20261105 2>/dev/null
echo "==== committed ===="
git log --oneline -2
echo "==== tracked files ===="
git ls-files | wc -l
