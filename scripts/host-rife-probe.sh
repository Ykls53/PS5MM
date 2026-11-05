#!/usr/bin/env bash
# Builds and runs the standalone RIFE probe under gdb, so a SIGSEGV shows the
# exact frame instead of just closing the socket.
set -uo pipefail
root=/home/yk/PS5MM
out="$root/build/host"
rife=/home/yk/ext/rife-ncnn/src
ncnn=/home/yk/ext/ncnn-rife
app="$root/ps5/app"
llama="$root/third_party/llama.cpp"

FLAGS="-std=c++20 -O1 -g -fPIC -fexceptions -frtti -DNCNN_VULKAN=1 -DNCNN_STATIC_DEFINE"
INC="-I $rife -I /tmp/rife-shd -I $ncnn/src -I $ncnn/build-hostvk/src -I /usr/include/vulkan -I $app -I $llama/vendor"

g++ $FLAGS $INC -c "$app/../host/rife_probe.cpp" -o "$out/obj/rife_probe.o"
g++ -o "$out/rife_probe" "$out/obj/rife_probe.o" "$out/librife-host.a" \
    "$ncnn/build-hostvk/src/libncnn.a" \
    -lglslang -lSPIRV -lMachineIndependent -lGenericCodeGen -lOSDependent \
    -lglslang-default-resource-limits -lSPIRV-Tools-opt -lSPIRV-Tools -lvulkan \
    -lpthread -ldl -lm -fopenmp
echo "built $out/rife_probe"
echo "==== run under gdb ===="
gdb -q -batch -ex run -ex 'bt 12' --args "$out/rife_probe" /data/PS5MM/rife 2>&1 | grep -vE '^\[Thread|^\[New Thread|debuginfod' | tail -30
