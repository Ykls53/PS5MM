#!/usr/bin/env bash
# 有没有远程仓库？本地 git 是什么状态？
set -uo pipefail
cd /home/yk/PS5MM || exit 1
echo "==== remote ===="
git remote -v 2>&1
echo "==== branches / tags ===="
git branch -a 2>&1
git tag 2>&1
echo "==== last commit ===="
git log --oneline -3 2>&1
echo "==== 工作区脏不脏 ===="
git status --porcelain 2>&1 | head -10
echo "==== 交付目录里的压缩包 ===="
ls -l /mnt/d/deepseekDAIGirlfriend/_research/PS5MM/deliver-20261105/*.zip 2>/dev/null
echo "==== 有没有 gh / git 凭据 ===="
command -v gh >/dev/null && gh auth status 2>&1 | head -5 || echo "(no gh cli)"
ls -la ~/.git-credentials 2>/dev/null || echo "(no ~/.git-credentials)"
git config --global user.name 2>&1
git config --global user.email 2>&1
