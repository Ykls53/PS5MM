#!/usr/bin/env python3
"""tts: 基线值 999 + 「没有 GPU 后端就降 0」的检测。

为什么两边都要：
  PS5 有 RADV → 999，全放 GPU（11-04 验收表：2.3 秒出 103 KB 音频）
  PC 的 llama 没编 Vulkan → 检测到没有 GPU 后端 → 0，正常跑 CPU

否则：PC 上 999 会让 llama 按不存在的设备算 buffer，ggml_abort 把整个进程带走
（今天已经踩过），于是 PC 根本没法验这条代码。
"""
from pathlib import Path

p = Path("/home/yk/PS5MM/ps5/app/tts_server.cpp")
s = p.read_text(encoding="utf-8")

OLD = """    mparams.n_gpu_layers = 999;   // 基线：11-04 验收表证明 GPU 上 2.3s 出音频
    if (const char * ngl = std::getenv("PS5MM_TTS_NGL"); ngl != nullptr && ngl[0] != 0) {
        mparams.n_gpu_layers = std::atoi(ngl);
    }
"""

NEW = """    mparams.n_gpu_layers = 999;   // 基线：11-04 验收表证明 GPU 上 2.3s 出音频
    // 没有 GPU 后端的构建（PC 验证版）不能声明 GPU 层：llama 会按一个不存在的
    // 设备去算 buffer，然后 ggml_abort 把整个进程带走。PS5 有 RADV，这条不触发。
    if (ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_GPU) == nullptr) {
        mparams.n_gpu_layers = 0;
    }
    if (const char * ngl = std::getenv("PS5MM_TTS_NGL"); ngl != nullptr && ngl[0] != 0) {
        mparams.n_gpu_layers = std::atoi(ngl);
    }
"""

if NEW in s:
    print("already applied")
elif s.count(OLD) != 1:
    raise SystemExit(f"anchor x{s.count(OLD)}; refusing")
else:
    p.write_text(s.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched: 999 + gpu detection")
