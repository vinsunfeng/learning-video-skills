# learning-video-skills

> **另一台机器上的 agent 要装这套东西？读 [`AGENT-START.md`](./AGENT-START.md)。**
> 那份是自助安装单，每步带验证方法 —— 包括两个实测踩过的错误安装路径，
> 以及**为什么不能用 `hermes skills list` 验证**。

把教学类视频变成**「不看视频、只凭文档就能复现」**的知识资产。

不是一个脚本，是一条带验收的流水线：本地观看引擎把视频读成转录+证据帧+索引，
编排 skill 把它蒸馏成带时间戳的笔记与可复现的操作手册，校验器与盲测负责把关，
最后可沿两条路线沉淀成**可被 agent 调用的 skill**。

```
用 video-distill 把这个视频沉淀成笔记：https://www.bilibili.com/video/BVxxxx
```

## 流水线

```
视频（YouTube / Bilibili / 本地文件）
  │  watch-skill 引擎：转录（whisper）· 抽帧 · OCR · 嵌入索引 —— 全本地，无静默付费
  ▼
video-distill skill（编排层，流程真源 SKILL.md）
  ├─ 阶段 0–1  预探测 / 全片转录（索引在这里定）
  ├─ 阶段 2    语义检索定 cue → 定点抽帧 → 分段读帧 → 逐字转写（专名以 OCR 为准）
  ├─ 阶段 2.4  盲测：干净 subagent 只拿 PLAYBOOK 复现，卡住的地方就是缺口
  ├─ 阶段 3    写入 Obsidian 三件套 + validate.py 闸门（0 错误才算交付）
  ▼
主笔记 + PLAYBOOK + EXTEND + transcript + 证据帧
  │  阶段 4 蒸馏（可选，按类型分流）
  ├─ 操作型 ─▶ PLAYBOOK 固化为项目内 skill
  └─ 方法论型 ─▶ transcript.md 原始转录 ─▶ cangjie-skill 六阶段蒸馏 ─▶ 编译成可调用 skill
```

**验证状态**（详见 `docs/experiments/`，每条带日期与判据）：
端到端实测 hermes 4 次、Claude 1 次；校验器双向有分辨力
（未填充模板 11 错+1 提醒 / 合格笔记 0 错 0 提醒）；盲测机制多轮实测
均抓到真问题（含故意种入的已知错误）。

## 产出长什么样

三件套 + 两个验收层：

| 产出 | 验收标准 |
|---|---|
| 主笔记 | 每条要点带可点击时间戳，跳回原片即凭据 |
| PLAYBOOK | **不看视频照着做完**；盲测 subagent 只拿它复现，卡住即缺口 |
| EXTEND | 扩展内容一律标 `[扩展]`、不带时间戳——「哪些话是讲者说的」机器可分 |
| validate.py | 时间戳锚点、hash、`engine_video_id` 等六条机械契约，真检查非存在性检查 |
| 盲测 | `validate.py` 满分 ≠ 手册可用——它查结构，查不出你有没有读对画面 |

## 安装

### 1. 引擎（watch-skill）

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

> **补丁是可选的加速，不是必需。** 非 Apple Silicon 的机器**不要**打。
> 详见 [`patches/README.md`](./patches/README.md)。
>
> **旧版 README 把它写成必做步骤，而补丁文件当时不在仓库里** ——
> 那是一条跑不通的指令，而**文档里跑不通的指令比没有文档更糟**。

为什么钉 3.11：这套栈全是二进制轮子，`onnxruntime` 是硬门槛。
**不要用 watch-skill 自带的 `curl install.sh | sh`** —— 它会挑系统 Python
（uv 官方的安装脚本无此问题）。uv 本体没装的话：
`curl -LsSf https://astral.sh/uv/install.sh | sh`，或发行版包管理器（Fedora `dnf install uv`）。

> 前置工具速查：**uv**（见上）、**ffmpeg**（`doctor` 自动补 deno/yt-dlp 有实测；
> 裸 Fedora 能否自补 ffmpeg 无记录，装不上就 `dnf install ffmpeg`）、
> **hermes CLI**（可选，装 Hermes 侧才需要——外部独立项目，本仓库不负责其安装；
> 下文凭证/视觉行为实测于 v0.21.0）。

### 2. 首次运行会下载的模型

| 模型 | 体积 | 用途 |
|---|---|---|
| `mlx-community/whisper-large-v3-turbo` | 1.5 GB | 本地转录（Apple GPU） |
| `paraphrase-multilingual-MiniLM-L12-v2` | 130 MB | 多语言嵌入，检索用 |
| RapidOCR PP-OCR 模型 | 随 ocr extra 附带 | 画面文字（含中日文） |

（上表为 Apple Silicon 路径；Linux/CUDA 机器由引擎按 GPU 选档，纯 CPU 机器见
AGENT-START §3 的模型档位说明——默认档中文质量不可用，必须显式降档。）

首次准备约 15~25 分钟。HF 未认证限速停滞时设 `HF_TOKEN` 或用
`huggingface_hub.snapshot_download(..., max_workers=4)` 续传。

### 3. skill 装到 agent

```bash
# Claude
mkdir -p ~/.claude/skills
ln -sfn "$REPO/.claude/skills/video-distill" ~/.claude/skills/video-distill

# Hermes：路径必须带 <category> 层，且新 profile 的 .env 是空模板（凭证不继承）
hermes profile create <name>        # 会预建 skills/<category> 分类目录（v0.21 实测）
hermes -p <name> setup              # 冷启动配凭证走这条；已有能跑 profile 时 cp 其 .env 更快
ln -sfn "$REPO/.claude/skills/video-distill" \
        ~/.hermes/profiles/<name>/skills/note-taking/video-distill
```

验证方法、两个实测踩过的错法、视觉模型（`auxiliary.vision`）配置——
都在 [`HERMES-INSTALL.md`](./HERMES-INSTALL.md)。核心纪律一句话：
**「装没装」问 agent 自己，「能不能读图」拿已知内容的帧考它——两个自述都作不了数。**

### 4. 可选：cangjie-skill（方法论蒸馏，阶段 4）

```bash
git clone https://github.com/kangarooking/cangjie-skill ~/.claude/skills/cangjie-skill
```

只有阶段 4 用得上。注意其脚本依赖 PyYAML（文档未声明）；交接契约
（转录进、笔记不进）见 SKILL.md 阶段 4 与
[`docs/experiments/cangjie-stage4-2026-09-08.md`](./docs/experiments/cangjie-stage4-2026-09-08.md)。

## 三个不会报错但会毁掉产出的坑

1. **分段观看必须 `--no-index`** —— `video_id = sha256(source)` 与时间范围无关，
   写索引前会 `DELETE` 该 id 的所有派生行，第 2 段会清空第 1 段。
2. **中文检索查询要写成空格分隔的 3 字以上词组** —— 引擎按空白切分且丢弃 <3 字的词，
   中文整句会退化成零命中，同时把置信度锚点压成 0。
3. **专有名词以 OCR 为准** —— 声学模型解决不了同音词（「短距」/「短剧」），
   画面文字才是可靠来源。

完整原理见 [`.claude/skills/video-distill/references/engine-internals.md`](./.claude/skills/video-distill/references/engine-internals.md)。

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

## 实测性能（M2 Pro，60s 中文音频）

| 后端 / 模型 | wall | RTF | 中文质量 |
|---|---|---|---|
| CT2 CPU `base`（**上游默认会选中这个**） | 4.2s | 0.07x | 繁体，错字密集 |
| CT2 CPU `medium` | 37.1s | 0.62x | 简体，准确 |
| **mlx `large-v3-turbo`（本配置）** | **2.8s** | **0.05x** | **简体准确** |

13.7 分钟视频的全片转录约 **41 秒**。跨语言检索实测：中文↔英文余弦相似度
0.5913 —— 中文提问可以命中英文转录。

## 仓库结构

```
.
├── .claude/skills/video-distill/      # skill 本体（软链到 agent 的 skills 目录即装）
│   ├── SKILL.md                       # 流程真源（每条规则带实测依据）
│   ├── templates/                     # 三件套模板
│   ├── scripts/                       # validate.py / blind_prep.py / trigger_test.py
│   ├── references/engine-internals.md # 引擎内部行为与实测数据
│   └── evals/                         # 触发评测样例（9 正 / 11 负）
├── patches/                           # watch-skill Apple Silicon 加速补丁（可选）
├── docs/
│   ├── experiments/                   # 全部实验记录（每次实测带日期、判据、边界）
│   └── superpowers/specs/             # 设计文档（引擎选型与决策依据）
├── AGENT-START.md / HERMES-INSTALL.md # 给别的机器上的 agent 的自助安装单
├── AGENTS.md                          # 工作约定唯一真源（含已验证事实清单）
├── HANDOFF-*.md                       # 停机交接：哪些已验证、哪些没有
└── HERMES-REAL-RUN.md / VERIFIED-ON-213.md  # 两份标志性实测记录
```

## 文档地图（按这个顺序读）

1. 本文件 —— 是什么、怎么装
2. [`AGENT-START.md`](./AGENT-START.md) —— 别的机器上的 agent 自助安装
3. [`.claude/skills/video-distill/SKILL.md`](./.claude/skills/video-distill/SKILL.md) —— **流程真源**
4. [`AGENTS.md`](./AGENTS.md) —— 工作约定与已验证事实（四档用词：已验证/观察到/推断/尚未验证）
5. [`HANDOFF-2026-09-08.md`](./HANDOFF-2026-09-08.md) —— 最近停机状态与下一步（各开放项对账见其中）
6. `docs/experiments/` —— 每次实验的原始记录

> 安装顺序说明：本节按「引擎 → skill」编号，而 AGENT-START §0 建议「先装 skill
> 再装引擎」（先知道装的东西拿来干什么）。两种顺序都装得起来，按你的习惯选。

## 退路

不想装 Python/uv 技术栈，或引擎出现无解 bug，可切回
[`bradautomates/claude-video`](https://github.com/bradautomates/claude-video)（两条 plugin 命令即可）。

代价：`--sub-langs "en.*"` 硬编码且**无配置项** → 中文视频拿不到原生字幕；
本地文件必走云端 Whisper（需 API key，单文件 25MB 上限）；无 OCR。
