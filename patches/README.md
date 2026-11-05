# patches/

PS5MM 相对上游的全部改动。GPL-3.0 要求发布二进制时提供完整源码；
`third_party/` 里就是**改过的完整源码**，这些 patch 让你看清改了哪几行。

2026-11-04 核对：下面 9 个 patch **逐个 `git apply --check --reverse` 全部通过**，
说明它们与实际工作区代码完全一致，不是过期文档。

## llama.cpp

上游 https://github.com/ggml-org/llama.cpp
基线 commit `04f7226a2c12c7f382c545a6db5a034266aa53cb`
全量改动：**15 个文件，+625 / −12 行**，另新增 2 个文件。

| # | patch | 干什么 |
|---|---|---|
| 1 | `0001-ps5-safe-cpu-defaults.patch` | PS5 CPU 的保守默认值（`common/common.cpp`） |
| 2 | `0002-ps5-thread-affinity-and-priority.patch` | 线程亲和性与优先级（`ggml/src/ggml-cpu/ggml-cpu.c`，+52） |
| 3 | `0003-tools-root.patch` | 把内置文件工具限制在 `LLAMA_TOOLS_ROOT` 沙箱里 |
| 4 | `0004-anthropic-system-messages.patch` | 非首位的 system 消息折进第一条（Claude Code 会发多条），Qwen 模板才收 |
| 5 | `0005-listener-survives-network-drops.patch` | 监听器在网络断开后存活（`server-http.cpp`） |
| 6 | `0006-jinja-tojson-floats-as-python.patch` | jinja `tojson` 的浮点格式对齐 Python |
| 7 | `0007-ps5lm-activity-hook.patch` | 活动钩子：电视界面要读的「正在生成 / 步数」 |
| 8 | `0008-log-never-blocks.patch` | 日志永不阻塞（PS5 上 stderr 每条一次 write 会把模型加载拖到 25 分钟） |
| 9 | `0009-introspection-logits-and-activations.patch` | 大件（+337 到 `server-context.cpp`）：内省端点、logits/激活统计，含新增的 `server-introspect.cpp/.h` |

### 怎么用

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp && git checkout 04f7226a2c12c7f382c545a6db5a034266aa53cb
for p in /path/to/patches/000*.patch; do git apply "$p"; done
```

## stable-diffusion.cpp

上游 https://github.com/leejet/stable-diffusion.cpp
基线 commit `cfed93e`（`master`）
**源码零改动** —— `git diff` 为 0 字节。

我们只做**链接层**处理：它和 llama.cpp 各带一份 ggml，重复符号约 18,666 个，
所以 `scripts/prefix-sd.sh` 用 `objcopy --redefine-syms` 给 sd 侧符号加 `SDX_` 前缀
（白名单保留 `sd_*` / `new_sd_ctx` / `generate_image` 等公开 API），
再补 `ps5/app/tls_stub.c` 填两个 TLS thunk。那是构建脚本的事，不是对上游源码的修改。

## mesa/

RADV（Vulkan 驱动）在 PS5 上的三个补丁，见 `mesa/README.md`：
被销毁 buffer 的内存等待、把提交放到独立线程、GPU 等待的自旋/睡眠策略。

## ps5-homebrew-ui

界面 kit，第三方项目（GPL-3.0-or-later，BlackBearReloaded）。
`third_party/ps5-homebrew-ui/` 是 vendored 拷贝，自带 LICENSE。
其 `assets/fonts/` 下的 `.huifont` 由 **Noto Sans SC（OFL 1.1）** 烘焙，
见同目录 `manrope-LICENSE.txt` / `Inter-LICENSE.txt` / `Montserrat-LICENSE.txt`。
**仓库内不含 simhei（中易黑体）产物。**
