#!/usr/bin/env bash
# Two checks that do not need the console:
#   1. the WAV reader on a real file
#   2. audio_server.cpp still parses (syntax/type check, no link)
set -uo pipefail
copy=/home/yk/PS5MM/ps5/host
root=/home/yk/PS5MM
app=$root/ps5/app
llama=$root/third_party/llama.cpp
out=$root/build/host
mkdir -p "$out/obj"

echo "==== 1. wav reader ===="
g++ -std=c++20 -O1 -o "$out/wav_read_test" "$copy/wav_read_test.cpp" || { echo "BUILD FAILED"; exit 1; }
"$out/wav_read_test" /tmp/tts-short1.wav || echo "read failed"
"$out/wav_read_test" /tmp/q2.wav || echo "read failed"

echo "==== 2. audio_server.cpp syntax check (with C API headers) ===="
g++ -std=c++20 -fsyntax-only \
    -I "$app" -I "$llama/vendor" -I "$llama/vendor/cpp-httplib" \
    -I /home/yk/ext/audio.cpp/include \
    "$app/audio_server.cpp" && echo "audio_server.cpp: OK"
