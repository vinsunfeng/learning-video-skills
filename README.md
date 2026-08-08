# video-distill

> **另一台机器上的 agent 要装这套东西？读 [`AGENT-START.md`](./AGENT-START.md)。**
> 那份是自助安装单，每步带验证方法 —— 包括两个实测踩过的错误安装路径，
> 以及**为什么不能用 `hermes skills list` 验证**。

把教学类视频沉淀成结构化、带时间戳、可回查的 Obsidian 笔记。

一个 Claude skill（编排层）+ 一个打了三个本地补丁的观看引擎（watch-skill）。
产出三件套：主笔记、可脱离视频复现的 PLAYBOOK、与视频原文严格分离的扩展阅读。

```
用 video-distill 把这个视频沉淀成笔记：https://www.bilibili.com/video/BVxxxx
```

## 仓库结构

```
.
├── .claude/skills/video-distill/     # skill 本体
│   ├── SKILL.md                      # 流程规范（软链到 ~/.claude/skills 后全局可用）
│   ├── templates/                    # 三件套模板
│   ├── scripts/validate.py           # 分层校验
│   └── references/engine-internals.md# 引擎内部行为与实测数据
├── vendor/watch-skill/               # 观看引擎，local-patches 分支
├── docs/superpowers/specs/           # 设计文档（含全部决策依据）
└── README.md
```

> **另一台机器上真装过一次**（2026-08-08，Fedora 44 / x86_64）：
> 结果与四个只有真装才会暴露的问题见 [`VERIFIED-ON-213.md`](./VERIFIED-ON-213.md)。
> 其中最要紧的一条：**`watch-skill` 在 PATH 里不等于它能干活。**

## 安装

### 1. 引擎

**用 uv 托管的 CPython 3.11，不要用系统 Python。**

**最省事：直接从上游装，不打补丁。**

```bash
uv tool install --python 3.11 "watch-skill[perceive,ocr,whisper,index]"
watch-skill doctor    # 自动补 ffmpeg / yt-dlp / deno
```

**Apple Silicon 想要加速**（转录走 GPU、OCR 走 CoreML）—— 再多两步：

```bash
git clone https://github.com/oxbshw/watch-skill.git /tmp/watch-skill
cd /tmp/watch-skill && git checkout -b local-patches
git apply --check "$REPO/patches/001-apple-silicon-accel.patch"   # 先干跑
git apply         "$REPO/patches/001-apple-silicon-accel.patch"

uv tool install --force --python 3.11 --with psutil --with mlx-whisper \
  --editable "$PWD"
watch-skill doctor
```

> **补丁是可选的加速，不是必需。** 不打也能跑，只是转录和 OCR 走 CPU 路径。
> 非 Apple Silicon 的机器**不要**打。详见 [`patches/README.md`](./patches/README.md)。
>
> **旧版 README 把它写成必做步骤，而补丁文件当时不在仓库里** ——
> 那是一条跑不通的指令，而**文档里跑不通的指令比没有文档更糟**。

为什么钉 3.11：这套栈全是二进制轮子。`onnxruntime` 是硬门槛且绕不过 —— OCR、
嵌入模型、以及 faster-whisper 自己的 VAD 都依赖它。3.11 的轮子覆盖最全；本机系统
Python 是 Homebrew 3.14，cp314 轮子的可用性未经确认，没必要赌。

**不要用 `curl install.sh | sh`** —— 它会挑系统 Python。

### 2. 首次运行会下载的模型

| 模型 | 体积 | 用途 |
|---|---|---|
| `mlx-community/whisper-large-v3-turbo` | 1.5 GB | 本地转录（Apple GPU） |
| `paraphrase-multilingual-MiniLM-L12-v2` | 130 MB | 多语言嵌入，检索用 |
| RapidOCR PP-OCR 模型 | 随 ocr extra 附带 | 画面文字（含中日文） |

首次准备约 15~25 分钟，主要是模型下载。HF 未认证限速时会停滞，设 `HF_TOKEN`
或用 `huggingface_hub.snapshot_download(..., max_workers=4)` 续传。

### 3. skill 软链到全局

```bash
ln -sfn "$REPO/.claude/skills/video-distill" ~/.claude/skills/video-distill
```

本 skill 与代码项目无关，需要在任意目录都能触发。

### 4. 可选：cangjie-skill（方法论蒸馏）

```bash
git clone https://github.com/kangarooking/cangjie-skill ~/.claude/skills/cangjie-skill
```

只有阶段 4 用得上，可以以后再装。

## 三个本地补丁

分支 `local-patches`，基线 `bf177b0`（2026-07-12）。上游更新时 rebase 这三个 commit。

| 补丁 | 解决什么 |
|---|---|
| **mlx-whisper 后端** | CTranslate2 架构上没有 Metal 后端，Apple GPU 完全闲置；且 `large-v3` 只在 NVIDIA 分支可达。新增 `transcribe/mlx_backend.py`，Apple Silicon 上优先走 GPU，失败自动回退 |
| **RapidOCR 开 CoreML** | `is_coreml_available()` 第一行就是 `if not self.cfg_use_coreml: return False`，而 `config.yaml` 出厂 `false`，上游从不设置 → OCR 一直跑 CPU EP。顺带把编译缓存移出 `/tmp`（macOS 会清理）。**实测收益仅约 9%**：PP-OCR 是动态输入形状，CoreML 编译不了、多数子图回退 CPU，不要按 GPU 加速预期 |
| **补装 psutil** | `_available_ram_gib()` 依赖 psutil，而它不在任何 extra 里 → 探测必然失败 → 任何 Apple Silicon 机器无论多少内存都落到 `base` 档 |

**未采纳**：放宽 `height<=720` 到 1440p。改一行格式串即可，对「看清代码」收益最大，
但会显著抬高下载体积与 token 成本，留待有明确需求时再开。

## 实测性能（M2 Pro，60s 中文音频）

| 后端 / 模型 | wall | RTF | 中文质量 |
|---|---|---|---|
| CT2 CPU `base`（**上游默认会选中这个**） | 4.2s | 0.07x | 繁体，错字密集 |
| CT2 CPU `medium` | 37.1s | 0.62x | 简体，准确 |
| **mlx `large-v3-turbo`（本配置）** | **2.8s** | **0.05x** | **简体准确** |

13.7 分钟视频的全片转录约 **41 秒**。

跨语言检索实测：中文↔英文余弦相似度 0.5913，无关中文句 -0.0285 —— 中文提问可以
命中英文转录。

## 环境变量

skill 会自动带上这些，手工调用引擎时也照抄：

```bash
env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u GEMINI_API_KEY -u OPENROUTER_API_KEY \
    WATCHSKILL_SUBTITLE_LANGS='zh.*' \
    WATCHSKILL_WHISPER_MODEL=large-v3-turbo \
    WATCHSKILL_CLOUD_STT_ENABLED=false \
    WATCHSKILL_COST_POLICY=offline_only \
    watch-skill <subcommand> ...
```

`env -u` 那一串不是多余的：带索引的 watch 会用 Haiku 描述最多 24 帧，**且不检查
`cost_policy`**，环境里有 key 就静默付费，CLI 没有开关可关。

英文视频临时改 `WATCHSKILL_SUBTITLE_LANGS='en.*'`。

## 三个不会报错但会毁掉产出的坑

1. **分段观看必须 `--no-index`** —— `video_id = sha256(source)` 与时间范围无关，
   写索引前会 `DELETE` 该 id 的所有派生行，第 2 段会清空第 1 段。
2. **中文检索查询要写成空格分隔的 3 字以上词组** —— 引擎按空白切分且丢弃 <3 字的词，
   中文整句会退化成零命中，同时把置信度锚点压成 0。
3. **专有名词以 OCR 为准** —— 声学模型解决不了同音词（「短距」/「短剧」），
   画面文字才是可靠来源。

完整原理见 `.claude/skills/video-distill/references/engine-internals.md`。

## 退路

不想装 Python/uv 技术栈，或引擎出现无解 bug，可切回
[`bradautomates/claude-video`](https://github.com/bradautomates/claude-video)（两条 plugin 命令即可）。

代价：`--sub-langs "en.*"` 硬编码且**无配置项** → 中文视频拿不到原生字幕；
本地文件必走云端 Whisper（需 API key，单文件 25MB 上限）；无 OCR。

## 设计文档

`docs/superpowers/specs/2026-07-31-video-distill-design-v3.md` —— 包含引擎选型对比、
每个决策的源码依据、以及从 v2 到 v3.4 的完整变更记录。
