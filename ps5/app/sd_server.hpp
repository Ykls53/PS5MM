// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

// PS5MM's picture engine: stable-diffusion.cpp behind A1111's /sdapi/v1/txt2img,
// its /sdapi/v1/txt2vid, the OpenAI image route, and a small video route.
//
// One context, one model, loaded on the first request and not before: on this
// console the model may be 10 GB, and the text and speech engines are already
// holding their own. Its own ggml; scripts/prefix-sd.sh keeps the two ggmls
// apart at link time.

#include <string>

struct SdModels {
    const char * diffusion;   // -m / --diffusion-model
    const char * clip_l;
    const char * clip_g;
    const char * t5xxl;
    const char * vae;
    const char * esrgan;   // ESRGAN-class upscaler, optional
    const char * output_dir;
    // 视频那一套（Wan 这类）。video_diffusion 为空 = 视频也用图像那套，
    // 跟以前一样；非空时 t5xxl / vae 缺省回退到上面那对。
    const char * video_diffusion;
    const char * video_t5xxl;
    const char * video_vae;
};

// Registers the routes and starts the listener; the model itself loads on the
// first request that needs it. Returns 0 when serving, -1 when the listener
// could not be opened.
int  sd_server_start(const SdModels & models, int port);

void sd_server_terminate(void);

// 启动时就加载模型（设置里勾了「启动加载」才调）。0 = 好了，-1 = 没加载上。
int  sd_server_preload(void);

void sd_server_progress(int * step, int * steps);   // 当前这一步 / 总共几步（0/0 = 没在跑）
bool sd_server_ready(void);       // the model is loaded
bool sd_server_listening(void);   // the port answers

std::string sd_server_state(void);
