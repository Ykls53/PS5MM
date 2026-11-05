#!/usr/bin/env bash
# PS5LM 电视端汉化：把中文字形烘成 dashboard 能加载的 SDF 字体。
#
# 为什么要两套字符集：界面文案的字只覆盖源码里出现过的那些，但聊天面板显示的是
# **模型生成的中文**，任意汉字都可能出现 —— 缺字形就是一片 ????。所以正文那个
# 字重（regular = manrope-500，聊天用的就是它）要装 GB2312 全集 6763 字。
#
#   CN_FONT=/path/to/NotoSansSC-VF.ttf scripts/bake-fonts-cn.sh
#
# 字体必须是 **TrueType 轮廓**（文件头 00 01 00 00）：stb_truetype 不认 CFF/OTF（OTTO）。
# 下载：
#   https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf
#
# 输出文件名保持 manrope-*.huifont 不变 —— main.cpp 的加载路径就不用动。
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
kit="$root/third_party/ps5-homebrew-ui"
src="${CN_FONT:-$root/.deps/fonts/NotoSansSC-VF.ttf}"
out="$root/ps5/app/assets/fonts"
tmp="$root/build/fonts"
mkdir -p "$tmp" "$out"

if [ ! -f "$src" ]; then
    echo "找不到字体: $src" >&2
    echo "下载：https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf" >&2
    echo "放到 .deps/fonts/NotoSansSC-VF.ttf，或用 CN_FONT=... 指定" >&2
    exit 2
fi

echo "== 1. 编译字体烘焙器 =="
# 编主仓库里那份（scripts/font-baker/bake_font.cpp），不是 submodule 里的原版 ——
# 原版不认 "@字符集文件"，而这个改动不值得单独养一个 submodule fork。
"${HOST_CXX:-clang++}" -std=c++20 -O2 -w "$root/scripts/font-baker/bake_font.cpp" -o "$tmp/bake_font"

echo "== 2. 生成两套字符集 =="
python3 "$root/scripts/gen-charset.py" "$root" "$tmp/charsets"
ui="$tmp/charsets/charset-ui.txt"
chat="$tmp/charsets/charset-chat.txt"

echo "== 3. 从可变字体取三个静态字重 =="
for weight in 200 500 600; do
    python3 -c 'import sys
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
instantiateVariableFont(TTFont(sys.argv[1]), {"wght": int(sys.argv[2])}).save(sys.argv[3])' \
        "$src" "$weight" "$tmp/noto-$weight.ttf"
done

echo "== 4. 烘焙 =="
# regular：聊天正文，GB2312 全集。36px + atlas 4096（2 的幂，任何 GL 都吃得下；
# 6763 字 × 约 48² ≈ 15.6M 像素，正好塞满 4096²）。36px 的 SDF 缩到界面正文的
# 20~26px 反而比 64px 更贴合。
"$tmp/bake_font" "$tmp/noto-500.ttf" "$out/manrope-500.huifont" 36 6 4096 "@$chat"
# semibold / display：界面标题与大数字，只装界面字集
"$tmp/bake_font" "$tmp/noto-600.ttf" "$out/manrope-600.huifont" 64 8 4096 "@$ui"
"$tmp/bake_font" "$tmp/noto-200.ttf" "$out/manrope-200.huifont" 64 8 4096 "@$ui"

echo "== 5. 结果 =="
ls -l "$out"/*.huifont
