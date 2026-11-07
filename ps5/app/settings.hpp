// What the user can change on the Settings page, kept in
// /data/PS5MM/settings.json. Unknown or missing keys keep their defaults, so
// an old file still loads after a new setting is added.
//
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace ps5lm {

struct Settings {
    bool        auto_load = false;  // load default_model at launch
    std::string default_model;      // a path from the library, or empty
    // 启动时加载清单：勾了的模型，启动那一刻就按 model_kind() 派给对应的引擎。
    // 主干模型（text / decision / speech / picture / video）才会被派；
    // 配件（projector / text-encoder / vae / upscaler）仍由各自的设置行决定。
    // 空 = 什么都不预加载，全等第一次请求或界面上手动起。
    std::vector<std::string> boot_models;
    uint32_t    ctx_cap   = 16384;  // the planner's longest context; three engines share the pool
    // 文字引擎的 slot 数：1 = 排队（请求一个一个来，KV 只占一份）；
    // 2 以上 = 并发（同时接 N 个，KV 要 N 份 —— 只有小模型/小上下文才撑得住）。
    int         parallel_slots = 1;
    // 槽位：端口 = 8001 + 槽位 - 1。谁占哪个槽位由这里定（1..5）。
    int         text_slot    = 1;
    int         picture_slot = 2;
    int         speech_slot  = 3;
    // 视频单独占一个槽位（8004 by default）。它和 picture_slot 走同一条
    // port_of_slot 路径，所以设置里照样能改端口。
    int         video_slot   = 4;
    std::string kv_type   = "auto"; // "auto", "f16", "q8_0" or "q4_0"
    bool        sounds    = true;
    bool        tools     = true;   // file tools in the browser chat, inside the scratch folder
    bool        introspect = false;  // POST /v1/introspect: raw logits and activations (off by default)
    uint32_t    scratch_limit_gib = 2;  // warn when the scratch folder grows past this
    std::string download_dir = "/data/PS5MM/models";  // where the market saves models

    // ---- the speech engine (Qwen3-TTS and whatever else mmproj audio takes) ----
    std::string tts_backbone = "/data/PS5MM/tts/backbone.gguf";
    std::string tts_mmproj   = "/data/PS5MM/tts/mmproj.gguf";
    std::string voices_dir   = "/data/PS5MM/voices";   // reference voices, one wav per "voice"
    std::string tts_lang     = "zh";

    // ---- the picture engine (stable-diffusion.cpp: images and video) ----
    // 图像和视频分开两个字段：sd.cpp 只有一个 --diffusion-model，但两边的模型
    // 通常不是同一个（画图用 SD/SDXL，出视频用 Wan）。视频为空就用图像那个。
    std::string sd_diffusion = "/data/PS5SD/models/diffusion_models/Wan2.2-TI2V-5B-Q8_0.gguf";
    std::string sd_video;
    // 视频那一套的另外两件。留空就沿用 sd_t5xxl / sd_vae（老配置的意思：
    // 视频和图像共用同一套编码器）；两套都填就不互相污染。
    std::string sd_video_t5xxl;
    std::string sd_video_vae;
    std::string sd_clip_l;
    std::string sd_clip_g;
    std::string sd_t5xxl     = "/data/PS5SD/models/text_encoders/umt5-xxl-encoder-Q4_K_M.gguf";
    std::string sd_vae       = "/data/PS5SD/models/vae/wan2.2_vae.safetensors";
    std::string sd_esrgan    = "/data/PS5MM/sd/esrgan.pth";
    int         sd_steps     = 20;
    int         sd_cfg_x10   = 50;   // cfg * 10, so the row can step by 0.5
    int         sd_width     = 832;
    int         sd_height    = 480;
    int         sd_frames    = 33;
    int         sd_fps       = 16;

    // ---- 帧插值（RIFE on ncnn+Vulkan）----
    // 默认关：ncnn 的 Vulkan 初始化在 PS5 上会把进程打死（见 interp_server.cpp）。
    // 关着的时候路由照在，但直接回 503，不碰 ncnn —— 所以是零性能损失。
    bool        interp_enabled = false;

    // ---- 音频引擎（audio.cpp）----
    // 之前是写死的；现在能指派。目录不存在就退回默认值，老配置不受影响。
    std::string audio_model = "/data/PS5MM/audio/model.gguf";
    std::string audio_dir   = "/data/PS5MM/audio";   // 渲染出来的 .wav 落这里
    // 语音现在就是 audio.cpp 的 qwen3_tts：克隆家族要一段参考音频 + 文字稿，
    // 否则第一次请求会被拒。留空则退化成「内置音色名」那条老路。
    std::string audio_voice_ref;
    std::string audio_voice_text;

    // ---- 3D 引擎（trellis.cpp）----
    // 7 个 GGUF 的目录；电视上不好选目录，改这里要编辑 settings.json。
    std::string trellis_dir = "/data/PS5MM/trellis";

    // ---- 性能旋钮（0 = 自动，由 caps 层按这台机器算）----
    // 冒烟测试就是靠这几项扫参数：改 settings.json、重开 app，不用重编。
    int         cpu_threads  = 0;   // 各引擎的 n_threads；自动 = 核数 - 1，夹 4..8
    int         vae_tile     = 0;   // VAE tile 边长；自动 = 512（池子小则 256）；0 显式写 -1 才关 tiling
    int         ubatch       = 0;   // llama 的 -ub；自动 = 池子 >= 11 GiB 时 512
    int         max_frames   = 0;   // 视频帧上限建议；自动按剩余池子算，夹 33..81
    bool        force_pro    = false;  // 设备名分辨不出 Pro，这开关强行按 Pro 档走

    bool operator==(const Settings &) const = default;
};

Settings load_settings(const char * path);
bool     save_settings(const char * path, const Settings & s);

}  // namespace ps5lm
