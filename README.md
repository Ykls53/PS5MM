# PS5MM

在一台 PS5 的**原生系统**上（不进 Linux），一个 title 里同时跑起三种本地引擎，
通过局域网给任何设备当模型服务器。

- **文字**：llama.cpp（`ggml-vulkan` + RADV），OpenAI / Anthropic 兼容
- **图像 / 视频**：stable-diffusion.cpp（自带一份 ggml）
- **语音**：llama.cpp 的 mtmd 跑 TTS

界面画在电视上（controller 操作），另外每个引擎都开 HTTP 端点给手机 / 电脑用。

> title id `PPSA99577`。数据在 `/data/PS5MM/`，模型可复用 `/data/PS5SD/models/`（只读）。

---

## 端口与槽位

**端口跟着槽位走，不跟引擎类型走**：五个槽位 → 8001~8005，谁占哪号由设置决定
（`settings.json` 的 `text_slot` / `picture_slot` / `speech_slot`，默认 1 / 2 / 3）。

| 槽位 | 默认端口 | 默认装什么 |
|---|---|---|
| 1 | 8001 | 文字（llama.cpp） |
| 2 | 8002 | 图像 / 视频（sd.cpp） |
| 3 | 8003 | 语音（TTS） |
| 4 / 5 | 8004 / 8005 | 预留 |

常用端点：

```bash
curl http://<PS5_IP>:8001/health
curl http://<PS5_IP>:8001/v1/models
curl -X POST http://<PS5_IP>:8001/v1/chat/completions -H 'Content-Type: application/json' -d '{...}'
curl -X POST http://<PS5_IP>:8002/sdapi/v1/txt2img -H 'Content-Type: application/json' -d '{...}'
curl -X POST http://<PS5_IP>:8002/sdapi/v1/txt2vid  -H 'Content-Type: application/json' -d '{...}'
curl -X POST http://<PS5_IP>:8003/v1/audio/speech     -H 'Content-Type: application/json' -d '{...}'
```

端点页（电视上按 R1 翻页）会列出全部路由和可直接复制的 curl，端口按当前槽位现算。

---

## 构建

只支持 **x86-64 Linux**。依赖链（一次性，慢在 RADV 和 ps5-opengl）：

1. `PS5_Vulkan` 及其分叉（`PS5_Mesa`、`PS5_PayloadSDK`），放在 `.deps/src/`，
   用它的 `tools/setup-native-dependencies.sh` 装、`tools/build-radv.sh release` 编，
   再 `make app` 拿 host 工具和 `libc.prx`
2. **ps5-opengl SDK**：`third_party/ps5-homebrew-ui/tools/fetch-opengl-sdk.sh` 会按 pin 的版本下载并校验 sha256
3. payload SDK：`scripts/setup-sdk.sh`

然后：

```bash
# 依赖就绪后
PS5_OPENGL_SDK=/path/to/ps5-opengl-sdk bash scripts/build-app.sh
```

产物在 `build/app-ps5/title/PPSA99577/`，`eboot.bin` 是 SELF（头 `4f153d1d`）。

Ubuntu / Debian 上需要的包：

```
build-essential clang llvm lld cmake ninja-build meson glslang-tools
python3-mako python3-yaml python3-packaging python3-setuptools
spirv-tools spirv-headers libvulkan-dev imagemagick ffmpeg
rsync libxml2-dev libelf-dev xxd python3-numpy python3-brotli librsvg2-dev lftp socat
```

### 不开 PS5 也能看界面

`scripts/preview-app-ui.sh` 用 Mesa 的 surfaceless EGL 在 PC 上离屏渲染 dashboard，
出的 PNG 和电视上是同一套绘制代码、同一批样例数据：

```bash
bash scripts/preview-app-ui.sh     # -> build/app-preview/*.png
```

### 字体

界面字体是 **Noto Sans SC**（SIL OFL 1.1，可商用）烘成的 SDF 位图字体：

```bash
CN_FONT=/path/to/NotoSansSC-VF.ttf bash scripts/bake-fonts-cn.sh
```

- 源字体必须是 **TrueType 轮廓**（`00010000`），`stb_truetype` 不认 CFF/OTF
- 正文那份装 **GB2312 全集**（6763 汉字），聊天面板显示模型生成的中文才不会出方框
- 标题两份装界面字集（由 `scripts/gen-charset.py` 从源码自动抽，**改文案要重跑**）

---

## 部署

产物是**一整个 title 文件夹**，用 ShadowMountPlus 挂到主屏（`/data/homebrew/PPSA99577/`）。

⚠ **字体不在 eboot 里**：`main.cpp` 的 `kAssets` 是 `/app0/assets`，字体按文件读。
换版本时这几样要一起传，只换 `eboot.bin` 界面还是旧字库：

```
/data/homebrew/PPSA99577/eboot.bin
/data/homebrew/PPSA99577/assets/fonts/manrope-200.huifont
/data/homebrew/PPSA99577/assets/fonts/manrope-500.huifont
/data/homebrew/PPSA99577/assets/fonts/manrope-600.huifont
```

换完要重新注册（先 `uninstall` 再 `scan`），主屏才会认新 eboot。

关 app 用 `/data/PS5MM/quit`（写个空文件），或电视上 **Options 键连按两下**。
**别直接 kill 渲染中的 title** —— 会让主机失联。

---

## 模型

**仓库里没有任何模型权重。** 全部自行下载，许可归各自发布者：

| 用途 | 我们用的 | 许可 |
|---|---|---|
| 文字 | Qwen3 系列 GGUF | Apache-2.0（以模型页为准） |
| 图像 / 视频 | Wan 2.2 + umt5 + VAE | 见各自模型页，有的限制商用 |
| 语音 | Qwen3-TTS | 见模型页 |

放到 `/data/PS5MM/models/`（或 `/data/PS5SD/models/` 复用），在电视界面里选。

---

## 许可

本项目 **GPL-3.0-or-later**，全文见 [LICENSE](LICENSE)。

它是 [cobanov/PS5LM](https://github.com/cobanov/PS5LM)（GPL-3.0）的衍生作品，
沿用同样的许可，并保留原项目的版权头。相对上游 llama.cpp / stable-diffusion.cpp
的全部改动见 [patches/](patches/)（每个 patch 都核对过与实际代码一致）。

发布二进制时，`third_party/` 里的完整源码即为对应源码。

### 第三方

| 组件 | 许可 |
|---|---|
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT |
| [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) | MIT |
| [ps5-homebrew-ui](https://github.com/BlackBearReloaded/ps5-homebrew-ui)（vendored） | GPL-3.0-or-later |
| Noto Sans SC（界面字体） | OFL 1.1 |
| DejaVu Sans Mono（日志 / 代码） | Bitstream Vera |
| cpp-httplib / nlohmann-json | MIT |
| stb | public domain |
| [ps5-exporter](https://github.com/Marice/ps5-exporter) v0.2.0（读温度/功耗） | GPL-3.0-or-later |

---

## 免责

**这不是索尼官方支持的功能。** 在 PS5 上跑自制 title 依赖社区漏洞，
可能违反服务条款、可能随系统更新失效、也可能带来你不想承担的风险。
自行判断，自负后果。不要在联机账号上使用，也不要让主机联网更新（固件一升，漏洞全废）。
