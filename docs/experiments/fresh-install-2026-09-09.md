# 基线安装指令真机验证（隔离环境）：2026-09-09

**问的问题**：README/AGENT-START 的基线安装命令（不打补丁路径），从零跑一遍能不能得到可干活的引擎？
——关闭 HANDOFF-2026-09-08「照当前文档的完整新机装机没真跑过」在本机可验证的部分
（Linux 特有环节仍以 213 的 8/8 实测为准）。

## 方法

`UV_TOOL_DIR` 隔离到 `video-distill-workspace/fresh-install/`，照文档原样命令
`uv tool install --python 3.11 "watch-skill[perceive,ocr,whisper,index]"`，
随后 doctor、import 循环、合成测试片端到端 watch。

## 结果

| 环节 | 结果 |
|---|---|
| 隔离安装 | ✅ watch-skill **1.4.3**（PyPI 当前版，> 文档基线 1.0.0），exit 0 |
| doctor | ✅ python 3.11.15 / ffmpeg / yt-dlp（**自更新成功**）/ deno 全 ok；新增「features warn」（mcp/loop/api extras 未装，属可选功能提示，非错误） |
| import 循环 | ✅ onnxruntime / rapidocr / faster_whisper / scenedetect 无一缺失（objc dylib 警告 = engine-internals §9 已知无害噪音） |
| 端到端 OCR | ✅ 合成片（Pillow 渲染 `HELLO FRESH INSTALL OCR` → ffmpeg loop 成 mp4）→ 隔离引擎 watch（`--no-index` + env 包装）→ **OCR 逐字读出全文** |

## 两个环境事实（记下备用）

1. **homebrew ffmpeg 没有 drawtext 滤镜**（`Filter not found`）——以后造合成测试片，
   用 watch-skill venv 自带的 Pillow 渲染 PNG 再 loop 成视频（本次走的路，脚本三行）。
2. doctor 在 1.4.3 会提示 mcp/loop/api 可选 extras——本流水线用不到，warn 可忽略。

## 结论与边界

- 文档基线安装路径（无补丁）在本机从零验证到 OCR 出活；引擎层「照文档能装」成立。
- 未覆盖：Apple 加速补丁路径本次未重测（其补丁命令对上游 1.4.3 是否 `git apply` 干净未验；
  上次验到 2026-08-08 通过）；Linux 特有环节以 213 实测为准。
- 测试产物：`video-distill-workspace/fresh-install/`（gitignore 覆盖）。
