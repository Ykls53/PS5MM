#!/usr/bin/env python3
"""Give the picture engine two model sets: images and video.

The bug this fixes: settings.json has had `sd_video` for a while, main.cpp even
passes it along, but sd_server.cpp never read it. Image and video share one
g_e.ctx, and ensure_ctx() only asked "is a context loaded?", never "is it the
right model?". So once the picture engine loaded the Wan set for a video, every
later txt2img ran on Wan's DiT + umt5 + Wan VAE -- images came out broken until
the app was restarted with the image set back in settings.

Now each request says which set it needs. A different set means unload, then
load: 12 GiB cannot hold an SD1.5 set (2.8 GB) and a Wan set (6.4 GB) at once,
so switching is a wait, not a crash. The antenna for the fallback: an empty
video set keeps the old behaviour (both use the image set).

    python3 patch-sd-modelsets.py [--check|--revert]
"""
import sys
from pathlib import Path

APP = Path("/home/yk/PS5MM/ps5/app")

EDITS = []


def edit(path: Path, old: str, new: str, tag: str) -> None:
    EDITS.append((path, old, new, tag))


# ---------------------------------------------------------------- settings.hpp
edit(
    APP / "settings.hpp",
    """    std::string sd_diffusion = "/data/PS5SD/models/diffusion_models/Wan2.2-TI2V-5B-Q8_0.gguf";
    std::string sd_video;
    std::string sd_clip_l;
    std::string sd_clip_g;
    std::string sd_t5xxl     = "/data/PS5SD/models/text_encoders/umt5-xxl-encoder-Q4_K_M.gguf";
    std::string sd_vae       = "/data/PS5SD/models/vae/wan2.2_vae.safetensors";
""",
    """    std::string sd_diffusion = "/data/PS5SD/models/diffusion_models/Wan2.2-TI2V-5B-Q8_0.gguf";
    std::string sd_video;
    // 视频那一套的另外两件。留空就沿用 sd_t5xxl / sd_vae（老配置的意思：
    // 视频和图像共用同一套编码器）；两套都填就不互相污染。
    std::string sd_video_t5xxl;
    std::string sd_video_vae;
    std::string sd_clip_l;
    std::string sd_clip_g;
    std::string sd_t5xxl     = "/data/PS5SD/models/text_encoders/umt5-xxl-encoder-Q4_K_M.gguf";
    std::string sd_vae       = "/data/PS5SD/models/vae/wan2.2_vae.safetensors";
""",
    "settings.hpp: fields",
)

# ---------------------------------------------------------------- settings.cpp
edit(
    APP / "settings.cpp",
    """    s.sd_video      = j.value("sd_video", s.sd_video);
""",
    """    s.sd_video      = j.value("sd_video", s.sd_video);
    s.sd_video_t5xxl = j.value("sd_video_t5xxl", s.sd_video_t5xxl);
    s.sd_video_vae   = j.value("sd_video_vae", s.sd_video_vae);
""",
    "settings.cpp: load",
)
edit(
    APP / "settings.cpp",
    """        { "sd_diffusion", s.sd_diffusion }, { "sd_video", s.sd_video },
""",
    """        { "sd_diffusion", s.sd_diffusion }, { "sd_video", s.sd_video },
        { "sd_video_t5xxl", s.sd_video_t5xxl }, { "sd_video_vae", s.sd_video_vae },
""",
    "settings.cpp: save",
)

# --------------------------------------------------------------- sd_server.hpp
edit(
    APP / "sd_server.hpp",
    """    const char * esrgan;   // ESRGAN-class upscaler, optional
    const char * output_dir;
};
""",
    """    const char * esrgan;   // ESRGAN-class upscaler, optional
    const char * output_dir;
    // 视频那一套（Wan 这类）。video_diffusion 为空 = 视频也用图像那套，
    // 跟以前一样；非空时 t5xxl / vae 缺省回退到上面那对。
    const char * video_diffusion;
    const char * video_t5xxl;
    const char * video_vae;
};
""",
    "sd_server.hpp: SdModels",
)

# --------------------------------------------------------------- sd_server.cpp
edit(
    APP / "sd_server.cpp",
    """    std::mutex      mu;   // one generation at a time, and guards both
""",
    """    // ---- 视频那一套（Wan）：为空就沿用图片那套 ------------------------
    // 两套模型不可能同时待在 12 GiB 的池子里（SD1.5 约 2.8 GB、Wan2.1 约 6.4 GB），
    // 所以「换一套」= 先 free_sd_ctx 再 new_sd_ctx。loaded_key 记住现在装的是谁。
    SdModels        video{};
    std::string     own_video[3];
    std::string     loaded_key;
    std::mutex      mu;   // one generation at a time, and guards both
""",
    "sd_server.cpp: Engine video set",
)

edit(
    APP / "sd_server.cpp",
    """        models.output_dir = src[6] != nullptr ? own[6].c_str() : nullptr;
    }
""",
    """        models.output_dir = src[6] != nullptr ? own[6].c_str() : nullptr;

        const char * vsrc[3] = { in.video_diffusion, in.video_t5xxl, in.video_vae };
        for (int i = 0; i < 3; ++i) {
            own_video[i] = vsrc[i] != nullptr ? vsrc[i] : "";
        }
        video.diffusion = vsrc[0] != nullptr ? own_video[0].c_str() : nullptr;
        video.t5xxl     = vsrc[1] != nullptr ? own_video[1].c_str() : nullptr;
        video.vae       = vsrc[2] != nullptr ? own_video[2].c_str() : nullptr;
    }

    // 这次请求要哪一套：视频且配了视频模型就是视频，否则图片。
    const SdModels & set_for(bool want_video) const {
        return (want_video && video.diffusion != nullptr && video.diffusion[0] != 0) ? video : models;
    }
""",
    "sd_server.cpp: take_models video",
)

# ensure_ctx: signature + fingerprint + unload-on-mismatch
edit(
    APP / "sd_server.cpp",
    """// Loads the model if it is not in yet. Called with g_e.mu held.
bool ensure_ctx(std::string & err) {
    if (g_e.ctx != nullptr) {
        return true;
    }
""",
    """// Loads the model this request needs, unloading the other set first.
// Called with g_e.mu held (the free/load pair must not race a generation).
bool ensure_ctx(bool want_video, std::string & err) {
    const SdModels & m = g_e.set_for(want_video);
    // 指纹 = 这一套的全部路径。换模型集（图片 <-> 视频）时它会变。
    std::string key;
    for (const char * p : { m.diffusion, m.clip_l, m.clip_g, m.t5xxl, m.vae }) {
        key += (p != nullptr ? p : "");
        key += '\\x1f';
    }
    if (g_e.ctx != nullptr) {
        if (g_e.loaded_key == key) {
            return true;
        }
        // 装着的不是这一套：先卸掉。sd.cpp 没有「换模型」的接口，
        // 而两套同时驻留又超出池子，所以只有这一条路。
        std::printf("ps5mm-sd: switching model set to %s, unloading the other one\\n",
                    want_video ? "video" : "image");
        std::fflush(nullptr);
        free_sd_ctx(g_e.ctx);
        g_e.ctx       = nullptr;
        g_e.ready     = false;
        g_e.loaded_key.clear();
    }
""",
    "sd_server.cpp: ensure_ctx head",
)

# ensure_ctx body: g_e.models -> m
for old, new, tag in [
    ("    if (g_e.models.diffusion == nullptr || g_e.models.diffusion[0] == 0) {",
     "    if (m.diffusion == nullptr || m.diffusion[0] == 0) {", "body: empty check"),
    ("        if (::stat(g_e.models.diffusion, &st) == 0 && st.st_size > 0 && pool_gib > 0.1) {",
     "        if (::stat(m.diffusion, &st) == 0 && st.st_size > 0 && pool_gib > 0.1) {", "body: stat"),
    ('    std::printf("ps5mm-sd: loading %s\\n", g_e.models.diffusion);',
     '    std::printf("ps5mm-sd: loading %s\\n", m.diffusion);', "body: log loading"),
    ("        const std::string mpath = g_e.models.diffusion;",
     "        const std::string mpath = m.diffusion;", "body: mpath"),
    ("""        const bool has_clip = (g_e.models.clip_l != nullptr && g_e.models.clip_l[0] != 0) ||
                              (g_e.models.clip_g != nullptr && g_e.models.clip_g[0] != 0);""",
     """        const bool has_clip = (m.clip_l != nullptr && m.clip_l[0] != 0) ||
                              (m.clip_g != nullptr && m.clip_g[0] != 0);""", "body: has_clip"),
    ("""            cp.model_path = g_e.models.diffusion;
            std::printf("ps5mm-sd: %s -> model_path (single-file checkpoint)\\n", g_e.models.diffusion);
        } else {
            cp.diffusion_model_path = g_e.models.diffusion;
            std::printf("ps5mm-sd: %s -> diffusion_model_path (split components)\\n", g_e.models.diffusion);""",
     """            cp.model_path = m.diffusion;
            std::printf("ps5mm-sd: %s -> model_path (single-file checkpoint)\\n", m.diffusion);
        } else {
            cp.diffusion_model_path = m.diffusion;
            std::printf("ps5mm-sd: %s -> diffusion_model_path (split components)\\n", m.diffusion);""",
     "body: path choice"),
    ("""    cp.clip_l_path = (g_e.models.clip_l != nullptr && g_e.models.clip_l[0] != 0) ? g_e.models.clip_l : nullptr;
    cp.clip_g_path = (g_e.models.clip_g != nullptr && g_e.models.clip_g[0] != 0) ? g_e.models.clip_g : nullptr;
    cp.t5xxl_path  = (g_e.models.t5xxl != nullptr && g_e.models.t5xxl[0] != 0) ? g_e.models.t5xxl : nullptr;
    cp.vae_path    = (g_e.models.vae != nullptr && g_e.models.vae[0] != 0) ? g_e.models.vae : nullptr;""",
     """    cp.clip_l_path = (m.clip_l != nullptr && m.clip_l[0] != 0) ? m.clip_l : nullptr;
    cp.clip_g_path = (m.clip_g != nullptr && m.clip_g[0] != 0) ? m.clip_g : nullptr;
    cp.t5xxl_path  = (m.t5xxl != nullptr && m.t5xxl[0] != 0) ? m.t5xxl : nullptr;
    cp.vae_path    = (m.vae != nullptr && m.vae[0] != 0) ? m.vae : nullptr;""",
     "body: component paths"),
    ('''        err = "could not load the model";
        std::printf("ps5mm-sd: could not load %s\\n", g_e.models.diffusion);''',
     '''        err = "could not load the model";
        std::printf("ps5mm-sd: could not load %s\\n", m.diffusion);''', "body: load failed log"),
]:
    edit(APP / "sd_server.cpp", old, new, tag)

edit(
    APP / "sd_server.cpp",
    """    g_e.ready = true;
    g_load_stuck.store(false);   // 这次真加载上了，上一次的判决作废""",
    """    g_e.ready      = true;
    g_e.loaded_key = key;        // 记住这一套，下一次请求才好判断要不要切换
    g_load_stuck.store(false);   // 这次真加载上了，上一次的判决作废""",
    "sd_server.cpp: remember key",
)

# call sites
edit(APP / "sd_server.cpp",
     """    if (!ensure_ctx(err)) {
        return false;
    }
    sd_img_gen_params_t gp;""",
     """    if (!ensure_ctx(false, err)) {
        return false;
    }
    sd_img_gen_params_t gp;""",
     "call site: draw_image")

edit(APP / "sd_server.cpp",
     """    if (!ensure_ctx(err)) {
        return false;
    }
    sd_vid_gen_params_t gp;""",
     """    if (!ensure_ctx(true, err)) {   // 视频要视频那一套；没配就退回图片那套
        return false;
    }
    sd_vid_gen_params_t gp;""",
     "call site: make_video")

edit(APP / "sd_server.cpp",
     """    if (!ensure_ctx(err)) {
        return false;
    }
    sd_image_t init{};""",
     """    if (!ensure_ctx(false, err)) {
        return false;
    }
    sd_image_t init{};""",
     "call site: draw_from_image")

edit(APP / "sd_server.cpp",
     """    if (!ensure_ctx(err)) {
        return false;
    }""",
     """    if (!ensure_ctx(false, err)) {
        return false;
    }""",
     "call site: preload")

# attribute a preload failure to the image set explicitly
edit(APP / "sd_server.cpp",
     """int sd_server_preload(void) {""",
     """// 启动时预加载的是「图片」那一套：设置里勾了画图模型就是这个意思。
// 视频那套仍然等第一次 txt2vid 再进来（两边互斥，见 ensure_ctx）。
int sd_server_preload(void) {""",
     "preload comment")

# health: say which set is live
edit(APP / "sd_server.cpp",
     """void on_health(const httplib::Request &, httplib::Response & res) {
    json out{ { "ok", true },
              { "engine", "picture" },
              { "model_loaded", g_e.ready },
              { "jobs", (long) g_e.jobs.load() },
              { "model", g_e.models.diffusion != nullptr ? g_e.models.diffusion : "" } };""",
     """void on_health(const httplib::Request &, httplib::Response & res) {
    json out{ { "ok", true },
              { "engine", "picture" },
              { "model_loaded", g_e.ready },
              { "jobs", (long) g_e.jobs.load() },
              { "model", g_e.models.diffusion != nullptr ? g_e.models.diffusion : "" },
              { "video_model", g_e.video.diffusion != nullptr ? g_e.video.diffusion : "" } };""",
     "health: video_model",
)

# ------------------------------------------------------------------ main.cpp
edit(
    APP / "main.cpp",
    """            SdModels sd_models{ sd_model.empty() ? nullptr : sd_model.c_str(),
                                sd_clip_l.empty() ? nullptr : sd_clip_l.c_str(),
                                sd_clip_g.empty() ? nullptr : sd_clip_g.c_str(),
                                sd_t5xxl.empty() ? nullptr : sd_t5xxl.c_str(),
                                sd_vae.empty() ? nullptr : sd_vae.c_str(),
                                sd_esrgan.empty() ? nullptr : sd_esrgan.c_str(), kOutputs };""",
    """            SdModels sd_models{ sd_model.empty() ? nullptr : sd_model.c_str(),
                                sd_clip_l.empty() ? nullptr : sd_clip_l.c_str(),
                                sd_clip_g.empty() ? nullptr : sd_clip_g.c_str(),
                                sd_t5xxl.empty() ? nullptr : sd_t5xxl.c_str(),
                                sd_vae.empty() ? nullptr : sd_vae.c_str(),
                                sd_esrgan.empty() ? nullptr : sd_esrgan.c_str(), kOutputs,
                                sd_video.empty() ? nullptr : sd_video.c_str(),
                                sd_video_t5xxl.empty() ? nullptr : sd_video_t5xxl.c_str(),
                                sd_video_vae.empty() ? nullptr : sd_video_vae.c_str() };""",
    "main.cpp: SdModels init",
)

edit(
    APP / "main.cpp",
    """        const std::string sd_t5xxl  = boot.sd_t5xxl,  sd_vae    = boot.sd_vae;""",
    """        const std::string sd_t5xxl  = boot.sd_t5xxl,  sd_vae    = boot.sd_vae;
        // 视频那一套的编码器：留空 = 沿用上面那对（老配置）。
        const std::string sd_video_t5xxl = boot.sd_video_t5xxl.empty() ? boot.sd_t5xxl : boot.sd_video_t5xxl;
        const std::string sd_video_vae   = boot.sd_video_vae.empty() ? boot.sd_vae : boot.sd_video_vae;""",
    "main.cpp: video t5/vae fallback",
)

edit(
    APP / "main.cpp",
    """        std::thread([sd_model, sd_video, sd_clip_l, sd_clip_g, sd_t5xxl, sd_vae, sd_esrgan, preload_picture, sd_slot] {""",
    """        std::thread([sd_model, sd_video, sd_clip_l, sd_clip_g, sd_t5xxl, sd_vae, sd_esrgan, sd_video_t5xxl,
                     sd_video_vae, preload_picture, sd_slot] {""",
    "main.cpp: thread capture",
)

edit(
    APP / "main.cpp",
    """            (void) sd_video;   // 视频模型由路由在出片时挑（见 sd_server 的 pick_model）
""",
    """            // 视频模型交给 sd_server：它按请求决定装哪一套（见 ensure_ctx）
""",
    "main.cpp: drop dead (void)",
)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--check":
        for path, old, new, tag in EDITS:
            src = path.read_text(encoding="utf-8")
            state = "applied" if new in src else ("todo" if old in src else "MISSING")
            print(f"{state:8s} {tag}")
        return 0
    if mode == "--revert":
        for path, old, new, tag in reversed(EDITS):
            src = path.read_text(encoding="utf-8")
            if new in src:
                path.write_text(src.replace(new, old, 1), encoding="utf-8")
        print("reverted")
        return 0

    failed = False
    for path, old, new, tag in EDITS:
        src = path.read_text(encoding="utf-8")
        if new in src:
            print(f"skip     {tag} (already applied)")
            continue
        n = src.count(old)
        if n != 1:
            print(f"FAILED   {tag}: anchor found {n} times", file=sys.stderr)
            failed = True
            continue
        path.write_text(src.replace(old, new, 1), encoding="utf-8")
        print(f"patched  {tag}")
    if failed:
        print("some edits failed; fix anchors before building", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
