#!/usr/bin/env python3
# Refresh stale UI text for VoxCPM / interpolation / unload.
#   --check / --revert
import pathlib, sys, shutil

p = pathlib.Path("/home/yk/PS5MM/ps5/app/dashboard.cpp")
bak = p.with_name(p.name + ".bak-text")
src = p.read_text(encoding="utf-8")

if "--revert" in sys.argv:
    if bak.exists():
        shutil.copyfile(bak, p)
        print("reverted")
    else:
        print("no backup")
    sys.exit(0)

chunks = [
    # speech engine descriptions
    ('{ Setting::tts_backbone, "语音模型", "Qwen3-TTS 的主 GGUF，说话的那一半" }',
     '{ Setting::tts_backbone, "语音模型", "VoxCPM 单文件 GGUF（talker + AudioVAE 都在这一个里）" }'),
    ('{ Setting::tts_mmproj, "codec", "和主模型配套的 mmproj，缺了说不出话" }',
     '{ Setting::tts_mmproj, "codec", "VoxCPM 不需要；老的 Qwen3-TTS 才要，留空即可" }'),
    ('{ Setting::voices_dir, "音色目录", "参考音色 wav 放这里，请求里写文件名" }',
     '{ Setting::voices_dir, "音色目录", "参考音色 wav 放这里，再放同名 .txt 写它的台词" }'),
    ('{ Setting::tts_lang, "语言", "说话用哪种语言；音色本身是中性的" }',
     '{ Setting::tts_lang, "语言", "预留；VoxCPM 按参考音色说中文" }'),
    # interpolation: measured working (256x256, 92 ms) — no longer "crashes on launch"
    ('{ Setting::interp_enabled, "补帧", "RIFE 走 ncnn+Vulkan，这台机器上一跑就崩；默认关，修好再开" }',
     '{ Setting::interp_enabled, "补帧", "RIFE 走 ncnn+Vulkan；实测 256×256 92 ms，8002 /media/v1/interpolate" }'),
    # model page hint
    ('"X 指派模型 · □ 加载／卸载 · 语音槽只随启动加载，图像槽没有运行中卸载"',
     '"X 指派模型 · □ 加载／卸载 · 语音槽只随启动加载，卸载后需重开 app"'),
    # comment above the language picker
    ('            // Qwen3-TTS 的音色是中性参考音，语种在这里点一句它就跟上',
     '            // 语言选项：VoxCPM 目前按参考音色的中文说话，这里先留着'),
]

if "--check" in sys.argv:
    for old, new in chunks:
        print(("OK  " if new in src else "MISS"), new[:60])
    sys.exit(0)

for old, new in chunks:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"anchor matched {n}: {old[:60]}")
    src = src.replace(old, new)

if not bak.exists():
    shutil.copyfile(p, bak)
p.write_text(src, encoding="utf-8")
print("patched dashboard text")
