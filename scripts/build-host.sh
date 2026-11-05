#!/usr/bin/env bash
# Builds PS5MM's engines as a host (x86-64 Linux) executable, for PC verification.
#
#   scripts/build-host.sh            -> build/host/ps5mm-host
#
# The engine sources are the console's, unchanged: none of them call a PS5 API.
# What differs is the platform layer (main.cpp/display.cpp are not compiled) and
# the two ggmls: sd.cpp's copy gets SDX_ prefixed, exactly as scripts/prefix-sd.sh
# does for the console build, so llama.cpp's ggml keeps the bare names.
#
# Optional engines appear when their libraries do; PS5MM_HOST_AUDIO/TRELLIS are
# defined only then. Nothing here needs root and nothing touches the console.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
out="$root/build/host"
llama="$root/third_party/llama.cpp"
sd="$root/third_party/stable-diffusion.cpp"
sggml="$sd/ggml"
app="$root/ps5/app"
hostsrc="$root/ps5/host"
CXX=${CXX:-g++}
FLAGS="-O2 -fexceptions -frtti"
JOBS=${JOBS:-$(nproc)}

mkdir -p "$out/obj" "$out/sdlibs" "$out/sdlibs/orig"

echo "build-host: sd libraries, SDX_ prefixed"
# Originals are kept once; every run starts from them, so re-running is safe.
for f in "$sd/build-x86/libstable-diffusion.a" \
         "$sd/build-x86/ggml/src/libggml.a" \
         "$sd/build-x86/ggml/src/libggml-cpu.a" \
         "$sd/build-x86/ggml/src/libggml-base.a"; do
    [ -f "$f" ] || { echo "build-host: missing $f (configure stable-diffusion.cpp's build-x86 first)" >&2; exit 2; }
    b=$(basename "$f")
    [ -f "$out/sdlibs/orig/$b" ] || cp -f "$f" "$out/sdlibs/orig/$b"
    cp -f "$out/sdlibs/orig/$b" "$out/sdlibs/$b"
done
rm -f "$out/sdlibs/rename.txt"
nm --defined-only -g "$out/sdlibs/libggml.a" "$out/sdlibs/libggml-cpu.a" "$out/sdlibs/libggml-base.a" 2>/dev/null |
    awk 'NF>=3 && $2 ~ /[TWVDBR]/{print $3}' | sort -u |
    grep -E '^ggml_' |
    awk '{print $1" SDX_"$1}' > "$out/sdlibs/rename.txt"
echo "build-host: $(wc -l < "$out/sdlibs/rename.txt") names get SDX_"
for a in "$out/sdlibs"/*.a; do
    objcopy --redefine-syms="$out/sdlibs/rename.txt" "$a" "$a.prefixed"
    mv -f "$a.prefixed" "$a"
done

defs=()
if [ -f "$out/libaudiocpp_c.a" ]; then
    defs+=(-DPS5MM_HOST_AUDIO)
fi
if [ -f "$out/libtrellis_core.a" ]; then
    defs+=(-DPS5MM_HOST_TRELLIS)
fi

echo "build-host: compiling app objects"
cxx() { $CXX -std=c++20 $FLAGS "${defs[@]}" -I "$llama/vendor" -I "$llama/vendor/cpp-httplib" "$@"; }

cxx -I "$app" -I "$llama/vendor" -c "$app/settings.cpp" -o "$out/obj/settings.o"
cxx -I "$llama/include" -I "$llama/ggml/include" -I "$app" -c "$app/adaptive.cpp" -o "$out/obj/adaptive.o"
cxx -I "$sd/include" -I "$sd/thirdparty" -I "$sggml/include" -I "$llama/vendor" \
    -c "$app/sd_server.cpp" -o "$out/obj/sd_server.o"
cxx -std=c++17 -I "$app" -I "$llama/vendor" -c "$app/media_server.cpp" -o "$out/obj/media_server.o"
cxx -I "$llama/include" -I "$llama/ggml/include" -I "$llama/tools/mtmd" -I "$llama/vendor" \
    -c "$app/tts_server.cpp" -o "$out/obj/tts_server.o"
cxx -I "$app" -I "$llama/vendor" -I "$hostsrc" -c "$hostsrc/host_main.cpp" -o "$out/obj/host_main.o"
cxx -I "$app" -I "$llama/vendor" -c "$hostsrc/tts_main.cpp" -o "$out/obj/tts_main.o"

# RIFE: real sources when ncnn is available, otherwise the honest stand-in.
rifelibs=()
if [ -f "$out/librife-host.a" ]; then
    echo "build-host: RIFE engine (ncnn) linked"
    rifelibs=("$out/librife-host.a" /home/yk/ext/ncnn-rife/build-hostvk/src/libncnn.a
              -lglslang -lSPIRV -lMachineIndependent -lGenericCodeGen -lOSDependent
              -lglslang-default-resource-limits -lSPIRV-Tools-opt -lSPIRV-Tools -lvulkan)
else
    echo "build-host: RIFE engine not built (no librife-host.a) - stub routes"
    cxx -I "$app" -I "$llama/vendor" -c "$hostsrc/interp_stub.cpp" -o "$out/obj/interp_stub.o"
    rifelibs=("$out/obj/interp_stub.o")
fi

if [[ " ${defs[*]-} " == *" -DPS5MM_HOST_AUDIO "* ]]; then
    echo "build-host: audio engine (audiocpp C API) linked"
    cxx -I "$app" -I "$llama/vendor" -c "$app/audio_server.cpp" -o "$out/obj/audio_server.o"
    audioobj=("$out/obj/audio_server.o" "$out/libaudiocpp_c.a")
else
    echo "build-host: audio engine not linked (build libaudiocpp_c.a first)"
    audioobj=()
fi

if [[ " ${defs[*]-} " == *" -DPS5MM_HOST_TRELLIS "* ]]; then
    echo "build-host: 3D engine (trellis) linked"
    cxx -I "$app" -I "$llama/vendor" -c "$app/trellis_server.cpp" -o "$out/obj/trellis_server.o"
    trellisobj=("$out/obj/trellis_server.o" "$out/libtrellis_core.a")
else
    echo "build-host: 3D engine not linked"
    trellisobj=()
fi

echo "build-host: linking"
# The speech engine gets its own, clean image: with sd's ggml and ncnn linked in,
# llama_model_load_from_file() aborts inside ggml_tallocr_alloc and takes the
# whole process with it. Same sources, no sd -- the model loads there.
$CXX -o "$out/ps5mm-tts" "$out/obj/tts_server.o" "$out/obj/tts_main.o" "$out/obj/settings.o" \
    -L "$llama/build-pc/bin" -lllama -lllama-common -lmtmd -lggml -lggml-base -lggml-cpu \
    -lpthread -ldl -lm
echo "build-host: $out/ps5mm-tts ($(stat -c %s "$out/ps5mm-tts") bytes)"

$CXX -o "$out/ps5mm-host" \
    "$out/obj/settings.o" "$out/obj/adaptive.o" "$out/obj/sd_server.o" "$out/obj/media_server.o" \
    "$out/obj/tts_server.o" "$out/obj/host_main.o" ${rifelibs[@]+"${rifelibs[@]}"} \
    ${audioobj[@]+"${audioobj[@]}"} ${trellisobj[@]+"${trellisobj[@]}"} \
    -Wl,--start-group "$out/sdlibs"/*.a -Wl,--end-group \
    -L "$llama/build-pc/bin" -lllama -lllama-common -lmtmd -lggml -lggml-base -lggml-cpu \
    -lavformat -lavcodec -lavutil -lswscale -lpthread -ldl -lm -fopenmp ${EXTRA_LIBS:-}
echo "build-host: $out/ps5mm-host ($(stat -c %s "$out/ps5mm-host") bytes)"
