#!/usr/bin/env bash
# 给 stable-diffusion.cpp 那一整套静态库里的 ggml 符号统一加 SDX_ 前缀，
# 定义和引用一起改；sd 自己的 API 与 sd:: 命名空间不动。
#
# 这样两份 ggml 在同一个二进制里各叫各的名字，不需要把库折成一个 object，
# 也就不会碰到 ld -r 造出的 weak undefined TLS thunk（_ZTH，SDK 不提供）。
#
#   scripts/prefix-sd.sh          （build/app-ps5/sd 已由 cmake 编好）
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
sdk=${PS5_PAYLOAD_SDK:-$root/.deps/src/PS5_Vulkan/.deps/native/ps5-payload-sdk}
out="$root/build/app-ps5/sd"
nm="$sdk/bin/llvm-nm"
objcopy="$sdk/bin/llvm-objcopy"

[ -d "$out" ] || { echo "prefix-sd: no $out" >&2; exit 2; }

orig="$out/orig"
mkdir -p "$orig"

# 相对路径清单：每个库在它原来的位置，原件在 $orig 下同名保存。
manifest="$out/archives.txt"
if [ ! -s "$manifest" ]; then
    find "$out" -name '*.a' ! -path "$orig/*" ! -name 'libps5mm_sd.a' -printf '%P\n' | sort > "$manifest"
    while read -r rel; do cp -f "$out/$rel" "$orig/$(echo "$rel" | tr '/' '_')"; done < "$manifest"
    echo "prefix-sd: originals saved ($(wc -l < "$manifest") archives)"
fi

libs=()
while read -r rel; do
    src="$orig/$(echo "$rel" | tr '/' '_')"
    cp -f "$src" "$out/$rel"          # 每次从原件开始
    libs+=("$out/$rel")
done < "$manifest"

# 1) sd 定义的全部 global 名字（T/W/V/D/B/R 都算），去掉公开 API 与 sd:: 命名空间
"$nm" --defined-only -g "${libs[@]}" 2>/dev/null |
    awk 'NF>=3 && $2 ~ /[TWVDBR]/{print $3}' | sort -u |
    grep -vE '^(sd_|new_sd_ctx|free_sd_ctx|generate_image|generate_video|upscale|new_upscaler_ctx|free_upscaler_ctx|get_upscale)' |
    grep -vE '_Z(TV|TI|TS|TH|TW|GV|GR)?N2sd' |
    awk '{print $1" SDX_"$1}' > "$out/rename.txt"
echo "prefix-sd: $(wc -l < "$out/rename.txt") names get SDX_"

# 2) 每个 archive 原地改名（--redefine-syms 同时改定义与引用）
for a in "${libs[@]}"; do
    "$objcopy" --redefine-syms="$out/rename.txt" "$a" "$a.prefixed"
    mv -f "$a.prefixed" "$a"
done

echo "prefix-sd: ${#libs[@]} prefixed archives ready"
