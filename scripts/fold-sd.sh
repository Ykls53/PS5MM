#!/usr/bin/env bash
# 把 stable-diffusion.cpp 的那一整套静态库折成单个 object，
# 只留它的 API（以及编译器为 TLS/虚表生成的 thunk）为 global。
# 两份 ggml 因此不会见面；llama.cpp 的 ggml 保留全局名字。
#
#   scripts/fold-sd.sh            （build/app-ps5/sd 已由 cmake 编好）
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
sdk=${PS5_PAYLOAD_SDK:-$root/.deps/src/PS5_Vulkan/.deps/native/ps5-payload-sdk}
out="$root/build/app-ps5/sd"
nm="$sdk/bin/llvm-nm"
ld="$sdk/bin/ld.lld"
objcopy="$sdk/bin/llvm-objcopy"
ar="$sdk/bin/llvm-ar"

[ -d "$out" ] || { echo "fold-sd: no $out; build the image engine first" >&2; exit 2; }

mapfile -t libs < <(find "$out" -name '*.a' ! -name 'libps5mm_sd.a' | sort)
[ ${#libs[@]} -gt 0 ] || { echo "fold-sd: no archives in $out" >&2; exit 2; }
echo "fold-sd: ${#libs[@]} archives"

# 1) 先用 sd.cpp 自己的 API 名字把库拉进来
"$nm" --defined-only -g "${libs[@]}" 2>/dev/null |
    awk 'NF>=3 && $2 ~ /[TWV]/{print $3}' |
    grep -E '^(sd_|new_sd_ctx|free_sd_ctx|generate_image|new_upscaler_ctx|free_upscaler_ctx)|_ZN2sd' |
    sort -u > "$out/api-seed.txt"
echo "fold-sd: $(wc -l < "$out/api-seed.txt") seed names"
us=()
while read -r n; do us+=(-u "$n"); done < "$out/api-seed.txt"
# --gc-sections here, not at the final link: it drops what only dead code
# referenced, which is where the weak undefined _ZTH TLS-init symbols come from
# (the console's emutls has no such init function, and the title converter
# refuses a binary that still names one).
"$ld" -r --gc-sections "${us[@]}" --start-group "${libs[@]}" --end-group -o "$out/sd_all.o"

# 2) 合并后再提一次：ld -r 会为 TLS 变量和虚表造出新的 thunk 名字
#    （_ZTH/_ZTW/_ZTV/_ZTI/_ZTS/__emutls_*），它们也得留成 global，
#    否则 title 转换器会说「没有 stub 提供这个符号」。
"$nm" --defined-only -g "$out/sd_all.o" 2>/dev/null |
    awk 'NF>=3 && $2 ~ /[TWVDRB]/{print $3}' |
    grep -E '^(sd_|new_sd_ctx|free_sd_ctx|generate_image|new_upscaler_ctx|free_upscaler_ctx|_ZT[HW]N2sd|__emutls.*N2sd)' |
    sort -u > "$out/api.txt"
echo "fold-sd: $(wc -l < "$out/api.txt") names stay global"

# 3) ld -r 为 TLS 变量生成的 _ZTH 是 local 的，白名单够不到它；单独提回 global
mapfile -t zth < <("$nm" "$out/sd_all.o" | awk 'NF>=3 && $3 ~ /^_ZTH/ {print $3}' | sort -u)
gz=()
for n in "${zth[@]}"; do gz+=("--globalize-symbol=$n"); done
echo "fold-sd: ${#zth[@]} TLS thunks back to global"
"$objcopy" --keep-global-symbols="$out/api.txt" "${gz[@]}" "$out/sd_all.o" "$out/sd_api.o"
rm -f "$out/sd_all.o" "$out/libps5mm_sd.a"
"$ar" rcs "$out/libps5mm_sd.a" "$out/sd_api.o"
echo "fold-sd: $out/libps5mm_sd.a ($(stat -c %s "$out/sd_api.o") bytes)"
