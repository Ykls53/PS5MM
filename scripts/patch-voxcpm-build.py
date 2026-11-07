#!/usr/bin/env python3
# Add the VoxCPM speech engine to PS5MM's build-app.sh.
#   --check  report whether the patch is present
#   --revert restore build-app.sh.bak-voxcpm
import pathlib, sys, shutil

p = pathlib.Path("/home/yk/PS5MM/scripts/build-app.sh")
bak = p.with_name("build-app.sh.bak-voxcpm")

if "--revert" in sys.argv:
    if bak.exists():
        shutil.copyfile(bak, p)
        print("reverted")
    else:
        print("no backup")
    sys.exit(0)

src = p.read_text(encoding="utf-8")

patches = []

# 1) Build VoxCPM right after stable-diffusion.cpp.
patches.append((
'''cmake --build "$out/sd" --target stable-diffusion
''',
'''cmake --build "$out/sd" --target stable-diffusion

# ---- the speech engine, second generation: VoxCPM.cpp, a third ggml ---------
# One GGUF (talker + AudioVAE), stateless per request, Vulkan only. Its ggml is
# the third copy in this image; scripts/prefix-voxcpm.sh renames everything
# outside the voxcpm:: namespace to VXC_ so the three copies coexist.
voxcpm_src=${VOXCPM_SRC:-/home/yk/VoxCPM.cpp}
if [ -d "$voxcpm_src" ]; then
    cmake -S "$voxcpm_src" -B "$out/voxcpm" -G Ninja \\
        -DCMAKE_TOOLCHAIN_FILE="$root/ps5/app/toolchain.cmake" \\
        -DCMAKE_BUILD_TYPE=Release \\
        -DCMAKE_C_FLAGS="$flags" -DCMAKE_CXX_FLAGS="$cxxflags" \\
        -DBUILD_SHARED_LIBS=OFF \\
        -DVOXCPM_VULKAN=ON -DVOXCPM_NATIVE=OFF \\
        -DVOXCPM_BUILD_EXAMPLES=OFF -DVOXCPM_BUILD_BENCHMARK=OFF -DVOXCPM_BUILD_TESTS=OFF \\
        -DVOXCPM_ENABLE_MP3=OFF -DVOXCPM_ENABLE_OPUS=OFF \\
        -DGGML_BACKEND_DL=OFF -DGGML_NATIVE=OFF -DGGML_CPU_ALL_VARIANTS=OFF \\
        -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON -DGGML_BMI2=ON -DGGML_AVX512=OFF \\
        -DGGML_OPENMP=OFF -DGGML_CCACHE=OFF \\
        -DVulkan_INCLUDE_DIR="$headers/include" -DVulkan_LIBRARY="$archive" \\
        -DVulkan_GLSLC_EXECUTABLE="$(command -v glslc)" -DSPIRV-Headers_DIR="$headers/cmake" \\
        -DMATH_LIBRARY=SceLibcInternal > "$out/voxcpm.configure.log" 2>&1 ||
        { tail -30 "$out/voxcpm.configure.log" >&2; exit 1; }
    cmake --build "$out/voxcpm" --target voxcpm
else
    echo "build-app: speech engine (VoxCPM): not linked (no $voxcpm_src)"
fi
''',
))

# 2) Adapter object next to the llama speech object.
patches.append((
'''cxx -std=c++20 -fexceptions -fcxx-exceptions -I "$llama/include" -I "$llama/ggml/include" -I "$llama/tools/mtmd" -I "$llama/vendor" -c "$root/ps5/app/tts_server.cpp" -o "$obj/tts_server.o"
''',
'''cxx -std=c++20 -fexceptions -fcxx-exceptions -I "$llama/include" -I "$llama/ggml/include" -I "$llama/tools/mtmd" -I "$llama/vendor" -c "$root/ps5/app/tts_server.cpp" -o "$obj/tts_server.o"
# The second speech engine: VoxCPM.cpp, same endpoint, Vulkan instead of CPU.
if [ -d "${VOXCPM_SRC:-/home/yk/VoxCPM.cpp}" ]; then
    cxx -std=c++20 -fexceptions -fcxx-exceptions \\
        -I "${VOXCPM_SRC:-/home/yk/VoxCPM.cpp}/include" -I "$root/third_party/ps5-homebrew-ui/src" \\
        -I "$llama/vendor" -c "$root/ps5/app/voxcpm_server.cpp" -o "$obj/voxcpm_server.o"
fi
''',
))

# 3) Prefix and collect the archives.
patches.append((
'''bash "$root/scripts/prefix-sd.sh"
sdlibs=()
''',
'''bash "$root/scripts/prefix-sd.sh"
sdlibs=()
# ---- the speech engine's ggml, VXC_ prefixed --------------------------------
voxlibs=()
if [ -d "$out/voxcpm" ]; then
    bash "$root/scripts/prefix-voxcpm.sh"
    while read -r rel; do voxlibs+=("$out/voxcpm/$rel"); done < "$out/voxcpm/archives.txt"
    echo "build-app: speech engine (VoxCPM): ${#voxlibs[@]} VXC_ archive(s)"
else
    echo "build-app: speech engine (VoxCPM): not linked"
fi
''',
))

# 4) Link: object + archives.
patches.append((
'"$obj/tts_server.o" "$obj/sd_server.o"',
'"$obj/tts_server.o" "$obj/voxcpm_server.o" "$obj/sd_server.o"',
))
patches.append((
'--start-group "${libs[@]}" "${sdlibs[@]}"',
'--start-group "${libs[@]}" "${sdlibs[@]}" ${voxlibs[@]+"${voxlibs[@]}"}',
))

if "--check" in sys.argv:
    for entry in patches:
        new = entry[1]
        print(("OK  " if new in src else "MISS"), new.splitlines()[0][:70])
    sys.exit(0)

for entry in patches:
    old, new = entry[0], entry[1]
    expect = entry[2] if len(entry) > 2 else 1
    n = src.count(old)
    if n != expect:
        raise SystemExit(f"anchor matched {n} times (expected {expect}): {old.splitlines()[0][:60]}")
    src = src.replace(old, new)

if not bak.exists():
    shutil.copyfile(p, bak)
p.write_text(src, encoding="utf-8")
print("patched build-app.sh")
