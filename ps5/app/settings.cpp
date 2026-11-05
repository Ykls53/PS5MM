// SPDX-License-Identifier: GPL-3.0-or-later
#include "settings.hpp"

#include <nlohmann/json.hpp>

#include <fstream>

namespace ps5lm {

Settings load_settings(const char * path) {
    Settings      s;
    std::ifstream in(path);
    if (!in) {
        return s;
    }
    const nlohmann::json j = nlohmann::json::parse(in, nullptr, false);
    if (!j.is_object()) {
        return s;
    }
    s.auto_load     = j.value("auto_load", s.auto_load);
    s.default_model = j.value("default_model", s.default_model);
    s.boot_models   = j.value("boot_models", s.boot_models);
    s.ctx_cap       = j.value("ctx_cap", s.ctx_cap);
    s.parallel_slots = j.value("parallel_slots", s.parallel_slots);
    s.text_slot      = j.value("text_slot", s.text_slot);
    s.picture_slot   = j.value("picture_slot", s.picture_slot);
    s.speech_slot    = j.value("speech_slot", s.speech_slot);
    s.kv_type       = j.value("kv_type", s.kv_type);
    s.sounds        = j.value("sounds", s.sounds);
    s.tools         = j.value("tools", s.tools);
    s.introspect    = j.value("introspect", s.introspect);
    s.scratch_limit_gib = j.value("scratch_limit_gib", s.scratch_limit_gib);
    s.download_dir  = j.value("download_dir", s.download_dir);
    s.tts_backbone  = j.value("tts_backbone", s.tts_backbone);
    s.tts_mmproj    = j.value("tts_mmproj", s.tts_mmproj);
    s.voices_dir    = j.value("voices_dir", s.voices_dir);
    s.tts_lang      = j.value("tts_lang", s.tts_lang);
    s.sd_diffusion  = j.value("sd_diffusion", s.sd_diffusion);
    s.sd_video      = j.value("sd_video", s.sd_video);
    s.sd_video_t5xxl = j.value("sd_video_t5xxl", s.sd_video_t5xxl);
    s.sd_video_vae   = j.value("sd_video_vae", s.sd_video_vae);
    s.sd_clip_l     = j.value("sd_clip_l", s.sd_clip_l);
    s.sd_clip_g     = j.value("sd_clip_g", s.sd_clip_g);
    s.sd_t5xxl      = j.value("sd_t5xxl", s.sd_t5xxl);
    s.sd_vae        = j.value("sd_vae", s.sd_vae);
    s.sd_esrgan     = j.value("sd_esrgan", s.sd_esrgan);
    s.sd_steps      = j.value("sd_steps", s.sd_steps);
    s.sd_cfg_x10    = j.value("sd_cfg_x10", s.sd_cfg_x10);
    s.sd_width      = j.value("sd_width", s.sd_width);
    s.sd_height     = j.value("sd_height", s.sd_height);
    s.sd_frames     = j.value("sd_frames", s.sd_frames);
    s.sd_fps        = j.value("sd_fps", s.sd_fps);
    s.cpu_threads   = j.value("cpu_threads", s.cpu_threads);
    s.vae_tile      = j.value("vae_tile", s.vae_tile);
    s.ubatch        = j.value("ubatch", s.ubatch);
    s.max_frames    = j.value("max_frames", s.max_frames);
    s.force_pro     = j.value("force_pro", s.force_pro);
    s.audio_model   = j.value("audio_model", s.audio_model);
    s.audio_voice_ref  = j.value("audio_voice_ref", s.audio_voice_ref);
    s.audio_voice_text = j.value("audio_voice_text", s.audio_voice_text);
    s.audio_dir     = j.value("audio_dir", s.audio_dir);
    s.trellis_dir   = j.value("trellis_dir", s.trellis_dir);
    s.interp_enabled = j.value("interp_enabled", s.interp_enabled);
    return s;
}

bool save_settings(const char * path, const Settings & s) {
    const nlohmann::json j = {
        { "auto_load", s.auto_load }, { "default_model", s.default_model },
        { "boot_models", s.boot_models }, { "ctx_cap", s.ctx_cap }, { "parallel_slots", s.parallel_slots },
        { "text_slot", s.text_slot }, { "picture_slot", s.picture_slot }, { "speech_slot", s.speech_slot },
        { "kv_type", s.kv_type },     { "sounds", s.sounds },       { "tools", s.tools },
        { "introspect", s.introspect },
        { "scratch_limit_gib", s.scratch_limit_gib }, { "download_dir", s.download_dir },
        { "tts_backbone", s.tts_backbone }, { "tts_mmproj", s.tts_mmproj },
        { "voices_dir", s.voices_dir },     { "tts_lang", s.tts_lang },
        { "sd_diffusion", s.sd_diffusion }, { "sd_video", s.sd_video },
        { "sd_video_t5xxl", s.sd_video_t5xxl }, { "sd_video_vae", s.sd_video_vae },
        { "sd_clip_l", s.sd_clip_l }, { "sd_clip_g", s.sd_clip_g },
        { "sd_t5xxl", s.sd_t5xxl },         { "sd_vae", s.sd_vae },       { "sd_esrgan", s.sd_esrgan },
        { "sd_steps", s.sd_steps },         { "sd_cfg_x10", s.sd_cfg_x10 },
        { "sd_width", s.sd_width },         { "sd_height", s.sd_height },
        { "sd_frames", s.sd_frames },       { "sd_fps", s.sd_fps },
        { "cpu_threads", s.cpu_threads },   { "vae_tile", s.vae_tile },
        { "ubatch", s.ubatch },             { "max_frames", s.max_frames },
        { "force_pro", s.force_pro },
        { "audio_model", s.audio_model },   { "audio_dir", s.audio_dir },
        { "audio_voice_ref", s.audio_voice_ref }, { "audio_voice_text", s.audio_voice_text },
        { "trellis_dir", s.trellis_dir },
        { "interp_enabled", s.interp_enabled },
    };
    std::ofstream out(path);
    out << j.dump(2) << "\n";
    return (bool) out;
}

}  // namespace ps5lm
