#!/usr/bin/env python3
# Drop the stale "音频模型 (audio.cpp)" settings row from the dashboard.
#   --check / --revert
import pathlib, sys, shutil

p = pathlib.Path("/home/yk/PS5MM/ps5/app/dashboard.cpp")
bak = p.with_name(p.name + ".bak-audio")
src = p.read_text(encoding="utf-8")

if "--revert" in sys.argv:
    if bak.exists():
        shutil.copyfile(bak, p)
        print("reverted")
    else:
        print("no backup")
    sys.exit(0)

chunks = [
    # enum entry
    ("    // 音频 / 3D 引擎的模型位置\n    audio_model,\n",
     "    // 3D 引擎（槽位 5）的模型位置\n"),
    # settings row in the platform category
    ("        { Setting::audio_model, \"音频模型\", \"audio.cpp 的 GGUF；没有就只起路由，等第一次请求\" },\n", ""),
    # category item count 7 -> 6 (anchor on the interp row so the other 7 doesn't match)
    ("        { Setting::interp_enabled, \"补帧\", \"RIFE 走 ncnn+Vulkan，这台机器上一跑就崩；默认关，修好再开\" } },\n      7 },",
     "        { Setting::interp_enabled, \"补帧\", \"RIFE 走 ncnn+Vulkan，这台机器上一跑就崩；默认关，修好再开\" } },\n      6 },"),
    # value display
    ("        case Setting::audio_model: {\n"
     "            if (s.audio_model.empty()) {\n"
     "                return \"无\";\n"
     "            }\n"
     "            const size_t slash = s.audio_model.find_last_of('/');\n"
     "            return slash == std::string::npos ? s.audio_model : s.audio_model.substr(slash + 1);\n"
     "        }\n", ""),
    # picker
    ("        case Setting::audio_model: {\n"
     "            Settings scratch = s;\n"
     "            add(\"默认 /data/PS5MM/audio/model.gguf\", \"放在 app 自己的目录里\",\n"
     "                scratch.audio_model == \"/data/PS5MM/audio/model.gguf\",\n"
     "                [](Settings & v) { v.audio_model = \"/data/PS5MM/audio/model.gguf\"; });\n"
     "            for (const auto & m : models) {\n"
     "                // audio.cpp 吃 gguf；别的扩展名别列进来\n"
     "                if (m.file.size() < 5 || m.file.rfind(\".gguf\") != m.file.size() - 5) {\n"
     "                    continue;\n"
     "                }\n"
     "                std::string name, build;\n"
     "                split_name(m.label, &name, &build);\n"
     "                add(name + \"  \" + build, gb(m.size_gib), scratch.audio_model == m.file,\n"
     "                    [file = m.file](Settings & v) { v.audio_model = file; });\n"
     "            }\n"
     "            break;\n"
     "        }\n", ""),
    # stale comment
    ("        // 槽位 3 是语音，槽位 4 是音频（audio.cpp 吃 gguf），槽位 5 是三维。\n",
     "        // 槽位 3 是语音，槽位 4 是视频，槽位 5 是三维。\n"),
]

if "--check" in sys.argv:
    for old, new in chunks:
        print(("OK  " if new in src else "MISS"), (new or old).splitlines()[0][:60])
    sys.exit(0)

for old, new in chunks:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"anchor matched {n}: {old.splitlines()[0][:60]}")
    src = src.replace(old, new)

if not bak.exists():
    shutil.copyfile(p, bak)
p.write_text(src, encoding="utf-8")
print("patched dashboard.cpp")
