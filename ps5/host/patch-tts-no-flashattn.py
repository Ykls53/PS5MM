#!/usr/bin/env python3
"""tts: turn flash attention off.

`app.log` 三次都停在 `init_audio` 之后，前面最后一行是 `warmup: flash attention is
enabled`。项目里已经有先例：sd_server 在 PS5 上 `flash_attn=true` 会 load 失败，
要关掉重试（sd_server.cpp:324-329）。tts 从来没设过这个字段，用的是 llama 的默认值。

CPU 后端本来就不支持 flash attention，所以 PC 上改这一行也不会退化 —— 正好可以先验。
"""
from pathlib import Path

p = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")
s = p.read_text(encoding="utf-8")

OLD = """    cparams.embeddings = true;   // gen_audio takes the hidden state of each sampled token
    cparams.no_perf    = true;"""

NEW = """    cparams.embeddings = true;   // gen_audio takes the hidden state of each sampled token
    cparams.no_perf    = true;
    // RADV 上 flash attention 有前科：sd_server 那边 flash_attn=true 会 load 失败，
    // 要关掉重试。tts 这一侧从没设过这个字段，用的是默认值，日志里明写
    // "warmup: flash attention is enabled"，而三次都卡在这之后。
    cparams.flash_attn = false;"""

if NEW in s:
    print("already applied")
elif s.count(OLD) != 1:
    raise SystemExit(f"anchor x{s.count(OLD)}; refusing")
else:
    p.write_text(s.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched: cparams.flash_attn = false")
