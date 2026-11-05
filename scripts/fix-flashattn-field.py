#!/usr/bin/env python3
"""flash_attn 字段在新版 llama 里是 flash_attn_type 枚举。"""
from pathlib import Path

p = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")
s = p.read_text(encoding="utf-8")
old = "    cparams.flash_attn = false;"
new = "    cparams.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED;"
print("count:", s.count(old))
if s.count(old) != 1:
    raise SystemExit("anchor missing")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("fixed to enum")
