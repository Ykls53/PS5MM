#!/usr/bin/env bash
# Builds the RIFE engine (rife.cpp + warp.cpp + interp_server.cpp) against the
# host ncnn, and folds it into build/host/librife-host.a so build-host.sh links
# it instead of the stub.
#
# NCNN_VULKAN must be on for the caller as well: it changes ncnn::Option's
# layout, and rife.h names ncnn::VulkanDevice. Runtime uses the CPU path
# (gpuid = -1), which is the part that runs on the console too.
set -uo pipefail

root=/home/yk/PS5MM
out="$root/build/host"
obj="$out/obj"
rife=/home/yk/ext/rife-ncnn/src
ncnn=/home/yk/ext/ncnn-rife
app="$root/ps5/app"
llama="$root/third_party/llama.cpp"

[ -f "$rife/rife.cpp" ] || { echo "no rife sources at $rife" >&2; exit 2; }
[ -f "$ncnn/build-hostvk/src/libncnn.a" ] || { echo "no host ncnn (run host-ncnn-build.sh)" >&2; exit 2; }

FLAGS="-std=c++17 -O2 -fPIC -fexceptions -frtti -DNCNN_VULKAN=1 -DNCNN_STATIC_DEFINE"
INC="-I $rife -I /tmp/rife-shd -I $ncnn/src -I $ncnn/build-hostvk/src -I /usr/include/vulkan -I $app -I $llama/vendor"

mkdir -p "$obj"
set -e
g++ $FLAGS $INC -c "$rife/rife.cpp" -o "$obj/rife.o"
g++ $FLAGS $INC -c "$rife/warp.cpp" -o "$obj/rife_warp.o"
# interp_server.cpp pulls settings.hpp, which defaults operator== (C++20).
g++ -std=c++20 -O2 -fPIC -fexceptions -frtti -DNCNN_VULKAN=1 -DNCNN_STATIC_DEFINE $INC \
    -c "$app/interp_server.cpp" -o "$obj/interp_server.o"
rm -f "$out/librife-host.a"
ar rcs "$out/librife-host.a" "$obj/rife.o" "$obj/rife_warp.o" "$obj/interp_server.o"
echo "rife: $out/librife-host.a ($(stat -c %s "$out/librife-host.a") bytes)"

# glslang, for ncnn's runtime shader compiler
libdir=/usr/lib/x86_64-linux-gnu
for a in libglslang.a libSPIRV.a libMachineIndependent.a libGenericCodeGen.a libOSDependent.a libglslang-default-resource-limits.a; do
    [ -f "$libdir/$a" ] && echo "rife: glslang part $a" || echo "rife: MISSING $libdir/$a"
done
