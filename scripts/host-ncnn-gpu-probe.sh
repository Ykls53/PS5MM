#!/usr/bin/env bash
# Build and run the ncnn GPU probe with the host ncnn (Vulkan ON).
set -uo pipefail
root=/home/yk/PS5MM
out="$root/build/host"
ncnn=/home/yk/ext/ncnn-rife
g++ -std=c++17 -O1 -fPIC -fexceptions -frtti -DNCNN_VULKAN=1 -DNCNN_STATIC_DEFINE \
    -I "$ncnn/src" -I "$ncnn/build-hostvk/src" -I /usr/include/vulkan \
    -c "$root/ps5/host/ncnn_gpu_probe.cpp" -o "$out/obj/ncnn_gpu_probe.o"
g++ -o "$out/ncnn_gpu_probe" "$out/obj/ncnn_gpu_probe.o" "$ncnn/build-hostvk/src/libncnn.a" \
    -lglslang -lSPIRV -lMachineIndependent -lGenericCodeGen -lOSDependent \
    -lglslang-default-resource-limits -lSPIRV-Tools-opt -lSPIRV-Tools -lvulkan \
    -lpthread -ldl -lm -fopenmp
echo "==== run ===="
timeout 120 "$out/ncnn_gpu_probe" 2>&1 | tail -10
echo "exit=$?"
