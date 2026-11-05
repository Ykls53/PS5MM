#!/usr/bin/env python3
"""Restore the speech engine's two baseline values.

11-04 验收表: tts 走 GPU（n_gpu_layers=999, mmproj on Vulkan），2.3 秒出 103 KB 音频。
我为了绕开两次锁死把它们钉到 CPU，那等于把一条有真机成绩的路换成没跑通的路。
退一步：先回到基线值，锁死的事另外查。
"""
from pathlib import Path

p = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")
s = p.read_text(encoding="utf-8")

a = "    mparams.n_gpu_layers = 0;"
b = "    mparams.n_gpu_layers = 999;   // 基线：11-04 验收表证明 GPU 上 2.3s 出音频"
c = "    mp.use_gpu             = false;"
d = "    mp.use_gpu             = true;"

print("anchors:", s.count(a), s.count(c))
if s.count(a) != 1 or s.count(c) != 1:
    raise SystemExit("anchor not unique; refusing")
s = s.replace(a, b, 1).replace(c, d, 1)
p.write_text(s, encoding="utf-8")
print("restored tts to baseline")
