// SPDX-License-Identifier: GPL-3.0-or-later
// PS5MM speech engine: VoxCPM.cpp (GGUF + ggml-vulkan), same OpenAI-compatible
// /v1/audio/speech endpoint as the llama.cpp Qwen3-TTS engine it replaces.
#pragma once

#include <string>

int         voxcpm_server_start(const char * model_path, const char * voices_dir, int port);
void        voxcpm_server_terminate(void);
bool        voxcpm_server_ready(void);
int         voxcpm_server_status(void);
bool        voxcpm_server_busy(void);
long        voxcpm_server_requests(void);
std::string voxcpm_server_state(void);
