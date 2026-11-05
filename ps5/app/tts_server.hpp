// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

// PS5MM's speech engine: Qwen3-TTS voice cloning (a backbone GGUF and an mmproj
// GGUF), behind OpenAI's /v1/audio/speech. It shares the process with the text
// and image engines and runs on threads of its own.
//
// The model loads once, at the start; a request that fails leaves the engine
// loaded for the next one.

#include <string>

// Loads the model, then serves on the port (non-blocking once it returns).
// Returns 0 when requests are being served, -1 when the model could not load:
// the caller keeps its other engines going either way.
int  tts_server_start(const char * backbone, const char * mmproj, const char * voices_dir, int port);

// Stops the listener and joins its thread. Called before the title ends.
void tts_server_terminate(void);

// True once requests are being served.
bool tts_server_ready(void);

// "backbone=... mmproj=... sample_rate=... requests=N", for the status page.
std::string tts_server_state(void);

// 结构化状态，给电视界面的槽位卡用：0 未配置/未开始，1 加载中，2 就绪，-1 加载失败。
int  tts_server_status(void);
// 配置了模型但文件缺失、引擎根本没起：标成失败，让界面说实话。
void tts_server_abandon(void);
// 启动以来回答的语音请求数。
long tts_server_requests(void);
// 正在合成一句话。
bool tts_server_busy(void);
