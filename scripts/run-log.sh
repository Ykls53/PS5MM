#!/usr/bin/env bash
# log filter + host dependency check, in one go
set -uo pipefail
echo "==== host log: model switching ===="
grep -nE 'switching model set|ps5mm-sd: loading|ps5mm-sd: loaded|txt2vid|picture\(s\)' /tmp/ps5mm-host.log | tail -20
echo "==== glslang / vulkan packages ===="
ls /usr/lib/x86_64-linux-gnu/libglslang* 2>/dev/null | head -5
ls /usr/include/vulkan/vulkan.h 2>/dev/null
ls /usr/lib/x86_64-linux-gnu/libvulkan.so* 2>/dev/null | head -3
ls /home/yk/ext/glslang/prefix/lib/cmake/glslang 2>/dev/null | head -3
echo "==== ncnn source revision ===="
git -C /home/yk/ext/ncnn-rife rev-parse --short HEAD 2>/dev/null
ls -d /home/yk/ext/ncnn-rife/build-* 2>/dev/null
