// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

// PS5MM's audio engine: audio.cpp's C ABI, on a third ggml, in the same
// process as the text, speech and picture engines.
//
// Its symbols are ACX_-prefixed at link time (scripts/prefix-audio.sh) so the
// three ggmls never meet; the 75 audiocpp_* functions stay unprefixed and are
// what this file calls.
//
// The model loads on the first request, not at the start: audio model families
// run to several GB and the other engines are already holding theirs.

#include <string>

struct AudioModels {
    const char * model;       // a .gguf, or the model's directory
    const char * task;        // tts / gen / clone / vc / ... (audiocpp's tokens)
    const char * output_dir;  // where rendered .wav files land
    // 克隆类模型（qwen3_tts Base 这类）要一段参考音频和它的文字稿，
    // 否则第一次请求就报 "requires voice clone reference audio"。
    const char * voice_ref;   // 参考 wav 的绝对路径，可空
    const char * voice_text;  // 上面那段 wav 说的是什么
};

// Registers the routes and starts the listener; the model loads on the first
// request that needs it. 0 = serving, -1 = the listener could not be opened.
int  audio_server_start(const AudioModels & models, int port);

void audio_server_terminate(void);

// Load the model now instead of on the first request. 0 = ready, -1 = failed.
int  audio_server_preload(void);

bool audio_server_ready(void);       // the model is loaded
bool audio_server_listening(void);   // the port answers

// Name of the loaded model family ("qwen3_tts", "ace_step", ...), or "".
std::string audio_server_family(void);

// Milliseconds the last render took, or 0 when nothing has run yet.
long audio_server_last_ms(void);
