#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
sdk=${PS5_PAYLOAD_SDK:-$root/.deps/src/PS5_Vulkan/.deps/native/ps5-payload-sdk}
out="$root/build/app-ps5/voxcpm"
nm="$sdk/bin/llvm-nm"
objcopy="$sdk/bin/llvm-objcopy"
[ -d "$out" ] || { echo "prefix-voxcpm: no $out" >&2; exit 2; }
orig="$out/orig"
mkdir -p "$orig"
manifest="$out/archives.txt"
if [ ! -s "$manifest" ]; then
    find "$out" -name '*.a' ! -path "$orig/*" -printf '%P\n' | sort > "$manifest"
    while read -r rel; do cp -f "$out/$rel" "$orig/$(echo "$rel" | tr '/' '_')"; done < "$manifest"
    echo "prefix-voxcpm: originals saved ($(wc -l < "$manifest") archives)"
fi
libs=()
while read -r rel; do
    src="$orig/$(echo "$rel" | tr '/' '_')"
    cp -f "$src" "$out/$rel"
    libs+=("$out/$rel")
done < "$manifest"
"$nm" --defined-only -g "${libs[@]}" 2>/dev/null |
    awk 'NF>=3 && $2 ~ /[TWVDBR]/{print $3}' | sort -u |
    grep -vE '6voxcpm' |
    grep -vE '^voxcpm_' |
    awk '{print $1" VXC_"$1}' > "$out/rename.txt"
echo "prefix-voxcpm: $(wc -l < "$out/rename.txt") names get VXC_"
for a in "${libs[@]}"; do
    "$objcopy" --redefine-syms="$out/rename.txt" "$a" "$a.prefixed"
    mv -f "$a.prefixed" "$a"
done
echo "prefix-voxcpm: ${#libs[@]} prefixed archives ready"