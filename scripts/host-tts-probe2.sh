#!/usr/bin/env bash
# Build the TTS probe and run it under gdb. If the model loader aborts, the
# backtrace names the exact function instead of leaving a bare SIGABRT.
set -uo pipefail
root=/home/yk/PS5MM
out="$root/build/host"
app="$root/ps5/app"
llama="$root/third_party/llama.cpp"
export LD_LIBRARY_PATH="$llama/build-pc/bin:${LD_LIBRARY_PATH:-}"
export PS5MM_TTS_NGL="${PS5MM_TTS_NGL:-0}"

g++ -std=c++20 -O1 -g -fexceptions -frtti \
    -I "$app" -I "$llama/include" -I "$llama/ggml/include" -I "$llama/tools/mtmd" \
    -I "$llama/vendor" -I "$llama/vendor/cpp-httplib" \
    -c "$root/ps5/host/tts_probe.cpp" -o "$out/obj/tts_probe.o"
g++ -o "$out/tts_probe" "$out/obj/tts_probe.o" "$out/obj/tts_server.o" \
    -L "$llama/build-pc/bin" -lllama -lllama-common -lmtmd -lggml -lggml-base -lggml-cpu \
    -lpthread -ldl -lm
echo "built $out/tts_probe"
gdb -q -batch -ex run -ex 'bt 18' --args "$out/tts_probe" 2>&1 |
    grep -vE '^\[Thread|^\[New Thread|debuginfod|^$' | tail -32
