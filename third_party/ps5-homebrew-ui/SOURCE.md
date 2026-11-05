# 这是 vendored 拷贝，不是本仓库的代码

- 上游：ps5-homebrew-ui（BlackBearReloaded），许可 **GPL-3.0-or-later**，全文见本目录 `LICENSE`
- 拷贝来源：本机开发树 `/home/yk/PS5SD/third_party/ps5-homebrew-ui`
- 拷贝日期：2026-11-04
- 为什么 vendored：原来是指向开发树的软链，开源后别人 clone 下来链接是断的

## 裁剪了什么（都不影响构建）

| 排除 | 体积 | 为什么 |
|---|---|---|
| `docs/` | 60 MB | 上游的文档媒体，不含代码 |
| `sce_sys/` | 32 MB | 上游自己的 PS5 打包素材；PS5MM 用 `ps5/app/sce_sys/` |
| `.deps/` `build/` | 1.6 MB | 构建缓存，`tools/fetch-opengl-sdk.sh` 会重新取 |
| `.git` | — | submodule 的 gitdir 指针，vendored 后无意义 |
| `*.bak-simhei` | — | **中易黑体（商业字体）的旧字体备份，不得随仓库分发** |

## ⚠ 字体

`assets/fonts/inter-*.huifont` 和 `montserrat-medium.huifont` 的字形来自
**Noto Sans SC（OFL 1.1）**，不是 Inter / Montserrat 本身（历史原因，文件名沿用了）。
2026-11-04 之前这三份是用 simhei 烘的，全部重烘过。
**任何时候都不要去软链 PS5SD 的 assets/fonts**（那边历史上是 simhei 污染源）。

## 改 kit 的注意事项

`tools/font-baker/bake_font.cpp` 的上游版本不认「@字符集文件」参数；
本仓库另有一份改造过的在 `../../scripts/font-baker/bake_font.cpp`，烘焙脚本用的是那份。
