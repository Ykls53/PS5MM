# PS5MM

[![中文](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-%E4%B8%AD%E6%96%87-4f8cff)](README.md)
[![English](https://img.shields.io/badge/lang-English-6b7280)](README.en.md)

**一台 PS5 上的全模态 AI 服务器。** 一个 native title、一个进程、一个 12 GB 内存池，
同时提供文字、图像、视频、语音克隆、三维、插帧六种能力——全部跑在主机自己的 GPU 上
（Vulkan / RADV，没有 CUDA）。

```
8001  文字    llama.cpp              OpenAI + Anthropic 双方言
8002  图像    stable-diffusion.cpp   A1111 兼容 + RIFE 插帧
8003  语音    VoxCPM.cpp             OpenAI TTS + 3 秒参考克隆
8004  视频    stable-diffusion.cpp   Wan，和 8002 共用 sd 上下文
8005  三维    trellis.cpp            图生 3D，出带 UV 的 GLB
8099  控制    /alive /quit
```

## 五个引擎

| # | 引擎 | 端口 | 能力 | 说明 |
|---|---|---|---|---|
| 1 | llama.cpp | 8001 | 文字 | OpenAI 与 Anthropic 双方言；放一个 `mmproj*.gguf` 就能看图 |
| 2 | stable-diffusion.cpp | 8002 | 图像 · 插帧 | SD/SDXL/Flux/Qwen-Image；RIFE 走 `/media/v1/interpolate` |
| 3 | VoxCPM.cpp | 8003 | 语音 | 0.5B GGUF，单文件，无状态，3 秒参考音频克隆 |
| 4 | stable-diffusion.cpp | 8004 | 视频 | Wan 系列，和图像互斥切换两套权重 |
| 5 | trellis.cpp | 8005 | 三维 | TRELLIS.2，一张图出 GLB |

图像和视频共用同一个 sd.cpp 引擎（互斥切换），所以是 **五个推理引擎、六个能力入口**。
端口跟槽位走（`text_slot / picture_slot / speech_slot / video_slot`），不是写死的。

## 真机实测（PS5 Pro，固件 13.42，内存池 12 GB）

| 能力 | 测试 | 结果 |
|---|---|---|
| 文字 | Qwen3 0.6B Q8_0 | 255.6 t/s 生成 |
| 图像 | 256×256 / 4 步 | 3.25 秒 |
| 视频 | 320×192 / 5 帧 / 4 步 | 30.5 秒 |
| 语音 | VoxCPM 0.5B q8_0，连发 10 句 | 2.6~4.1 秒/句，零退化 |
| 三维 | 512 / decim=64 | 281.8 秒，10.5 MB GLB |
| 插帧 | RIFE 256×256 | 92 ms |

语音是这轮的重点：旧的 Qwen3-TTS 第 2 句起从 5 秒掉到 72~98 秒，必须重启进程才能恢复；
换成 VoxCPM 后同进程连发 10 句稳定在 3 秒级。eboot 305 MB（含五套引擎）。

## 接口

```bash
# 文字（OpenAI 兼容）
curl http://<IP>:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"local","messages":[{"role":"user","content":"hello"}]}'

# 文字（Anthropic 兼容，可直接接 Claude Code）
curl http://<IP>:8001/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"model":"local","max_tokens":256,"messages":[{"role":"user","content":"hello"}]}'

# 图像
curl http://<IP>:8002/sdapi/v1/txt2img \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"a lighthouse at dusk","width":832,"height":480,"steps":20}'

# 视频（5 帧最小示例）
curl http://<IP>:8004/sdapi/v1/txt2vid \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"a cat walking","width":320,"height":192,"frames":5,"steps":4}' \
  --output out.avi

# 语音（参考音色：/data/PS5MM/voices/<名字>.wav + 同名 .txt 写台词）
curl http://<IP>:8003/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"input":"你好，我是主机里的声音","voice":"taiyi.wav"}' \
  --output hello.wav

# 图生 3D
curl http://<IP>:8005/v1/images/to3d \
  -H 'Content-Type: application/json' \
  -d '{"image":"<base64 png>","resolution":512,"decim":64}' \
  --output model.glb

# 插帧
curl http://<IP>:8002/media/v1/interpolate \
  -H 'Content-Type: application/json' \
  -d '{"frame0":"<base64>","frame1":"<base64>","timestep":0.5}'

# 卸载模型（换模型、腾内存不用重启）
curl -X POST http://<IP>:8002/unload
curl -X POST http://<IP>:8003/unload
```

## 快速开始

前提：一台能跑 homebrew 的 PS5（固件 13.x），已注入 TacHen + ShadowMountPlus + ftpsrv（2121）。

1. 把 `PPSA99577/` 整个目录传到 `/data/homebrew/`
2. 触发扫描：`POST http://<IP>:10101/api/v1/scan`，body `{"reset_attempts":true}`
3. 主屏出现「PS5MM」图标，点开
4. 模型放进 `/data/PS5MM/models/`（文字）、`/data/PS5MM/sd/`（图像/视频）、
   `/data/PS5MM/tts/`（语音）、`/data/PS5MM/trellis/`（三维），
   或在应用的「模型 → 搜索」里直接从 HuggingFace 下载
5. 语音还要放参考音：`/data/PS5MM/voices/<名字>.wav` + 同名 `.txt`
6. 设置里调好槽位和模型路径，重开 app

## 已知限制

- 11~12 GB 池子装不下三个大模型：文字 + 语音（约 2.1 GB）可以并发，再加图像/视频/三维中的任何一个就该停手
- 一次只加载一个模型；换模型前先 `POST /unload`
- 语音输出 16 kHz（VoxCPM 原生）
- 没有鉴权，别把端口暴露到公网
- 要越狱主机；越狱不持久，重启后要重新注入
- 原生 title 占着显示层，PS 键回主屏不可用（Options 连按两下退出）

## 许可

GPL-3.0-or-later。本项目衍生自 [cobanov/PS5LM](https://github.com/cobanov/PS5LM)（GPL-3.0）。

## 关于这个版本

这是**测试版本**，不保证稳定。我们已经把五个引擎、六个能力全部真机跑过一轮
（文字 / 图像 / 视频 / 语音克隆 / 三维 / 插帧），但边界情况、长时间运行、
不同固件版本下的问题一定还有。遇到 bug、崩进程、模型加载失败，欢迎开 issue 反馈。

## 来源与致谢

本项目的**前端框架直接基于 [PS5LM](https://github.com/cobanov/PS5LM) 的框架**
（native title 骨架、界面 kit、设置与模型管理那一套），感谢原作者 cobanov
以 GPL-3.0 开源；[PS5SD](https://github.com/Darkatek7/PS5SD) 是同在 PS5 上的
stable-diffusion.cpp 项目，本项目的图像/视频引擎方案参考了它。两个都是 PS5
homebrew 项目，代码和思路都给了很大帮助。

其余致谢：llama.cpp（ggml / llama-server / mtmd）、stable-diffusion.cpp、
VoxCPM.cpp（bluryar）与 VoxCPM（OpenBMB）、trellis.cpp（TRELLIS.2）、
ps5-homebrew-ui、Noto Sans SC、PS5_Vulkan / PS5_Mesa（RADV）、ps5-payload-sdk、
TacHen、ShadowMountPlus、ftpsrv。
没有这些项目，PS5 上跑推理仍然只是「有人试过」。
