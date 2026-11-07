#!/usr/bin/env bash
# mctx（投影器上下文）在整个进程里只初始化一次吗？
set -uo pipefail
A=/home/yk/PS5MM/ps5/app
echo "==== tts_server 里 mctx 的创建处 ===="
grep -n 'mctx\|mtmd_init\|mtmd_free' "$A/tts_server.cpp"

echo
echo "==== mtmd_helper gen_audio 里对 mctx 做了什么（encode_speaker / 首帧）===="
F=/home/yk/PS5MM/third_party/llama.cpp/tools/mtmd/mtmd-helper-gen.cpp
sed -n '367,430p' "$F"
