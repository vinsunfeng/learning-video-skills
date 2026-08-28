# AGENTS.md —— 这个项目的工作约定（唯一真源）

本文件是这个仓库的**唯一规则来源**。`CLAUDE.md` 刻意不含规则，只指向这里。
理由见 `CLAUDE.md`：同一条规则存两份，副本一定会漂移，而漂移的那一刻没人会知道。

项目是什么：把教学视频变成「不看视频、只凭文档就能复现」的知识资产。
产出是 `video-distill` 这个 skill（`.claude/skills/video-distill/`），
以及让**别的机器上的 agent 自己装上它**的一套文档。
仓库已公开：`https://github.com/vinsunfeng/learning-video-skills`

---

## 一、先读这几份，顺序不要变

1. **本文件** —— 工作约定、已验证事实、纪律
2. [`HANDOFF-2026-08-28.md`](./HANDOFF-2026-08-28.md) —— 最近一次停机状态、
   哪些已验证、哪些**没验证**、下一步顺序
   （上一份 [`HANDOFF-2026-08-08.md`](./HANDOFF-2026-08-08.md) 的 P0/P1/P2 已全部处理）
3. [`.claude/skills/video-distill/SKILL.md`](./.claude/skills/video-distill/SKILL.md)
   —— **流程真源**。不要凭别的文档猜它怎么工作
4. [`HERMES-REAL-RUN.md`](./HERMES-REAL-RUN.md) —— 真实跑一个 29 分钟教程的六轮实验记录
5. [`VERIFIED-ON-213.md`](./VERIFIED-ON-213.md) —— 在另一台机器（Fedora）上从零装一次的结果
6. [`AGENT-START.md`](./AGENT-START.md) / [`HERMES-INSTALL.md`](./HERMES-INSTALL.md)
   —— 给**别人**看的安装单。改动它们之前先想：远程 agent 照这条命令跑得通吗

---

## 二、证据纪律（这一节最重要）

### 2.1 用词只有四档，不许混

| 用词 | 含义 |
|---|---|
| **已验证** | 我跑过，且**有对照**（正/负、或已知变化）。写下数字与日期 |
| **观察到** | 跑过一次，n=1，没有对照 |
| **推断** | 从代码或已验证事实推出来的，**没实测** |
| **尚未验证** | 不知道。**这一档必须显式写出来，不许留白让人误以为验过** |

「我这次没看到」**不等于**「它不存在」。
2026-08-06 我 dump 了 519,810 字节场景树、写下「没有玩家 ID」——
而 ID 在一个按需创建的面板里。**Cocos 节点没打开就不在树里。**

### 2.2 先找仪器，再下结论；找到之后再问一句：这个仪器看得见我要找的东西吗

**本项目里已确认会说谎的仪器**（每一个都真的骗过我）：

| 仪器 | 谎言 |
|---|---|
| `hermes skills list` | 只列注册表来源，**本地软链进去的 skill 不出现** |
| `hermes prompt-size` 的 "Skills by size" 列表 | 同样漏本地 skill —— 但**它的 `skills index` 字节数看得见**（同一工具里两个仪器，一个瞎一个不瞎） |
| `watch-skill doctor` | 全报 `ok`，而**抽帧通路是坏的**（缺 `perceive` extra 它不检查） |
| `claude auth status` | `"loggedIn": true`，而真调用 **401 过期** |
| `skill-creator/run_loop` | 每条 `rate=0/3` 却照打 `[PASS]`/`[FAIL]`，看着像「准确率 55%」，**其实一次都没测到** |
| agent 的自述 | 问「有没有排除清单」它答「没有」；让它**逐字背**，它背全了 |

> **量错地方，会得到一个干净的、完全错误的答案。**

### 2.3 三条硬纪律

1. **先验证仪器能看见一个已知的变化，再拿它看未知的。**
   做法：park / restore（把东西拿掉，看数字是否回落）；或**故意种入一个已知错误**，
   看仪器抓不抓得到。
2. **先证明处理施加了，再读因变量。**
   例：换 whisper 模型要先在日志里看到 `model=medium device=cpu`，再读转录质量。
3. **已知对照要对着你要测的那个量做**，不是对着它的前置条件做。

### 2.4 这些形状的错误今天各出现过一次以上，看到就停手

- **会自己命中的过滤器**（第 3 次）：`pgrep -af "watch-skill watch"` 匹配到自己的
  ssh 命令行；`pkill -f` 同样自匹配**杀掉自己的 shell**；在整个流缓冲里找 skill 名，
  而缓冲里有「全部可用 skill 清单」⇒「写个快排」被判成触发 video-distill。
- **静默产出空结果的检查**：脚本里用了 macOS 没有的 `timeout`，四条检查全输出空行——
  **空行看起来就像「没问题」**。
- **`py_compile` 过不代表能跑**：全量字符串替换把 helper 写成无限递归，编译通过。
- **分数会骗人，理由不会**：8/9 和 4/11 差点让我去改 description，
  而理由栏写着「匹配 youtube-content skill」——问句压根没点名那个 skill。
- **一个所有臂都满分（或全 0）的测试，测不出任何东西。**
- **只在一种环境里验过的结论，写成普适的那一刻就变成了错的。**

### 2.5 中间产物不许放 `/tmp`

2026-08-08 一轮 20 条的对比测试跑到一半，`/tmp` 被清空，**日志与结果全部丢失**。
落盘位置：`docs/experiments/`（要留档）或 `.gitignore` 覆盖的
`video-distill-workspace/`（临时但不丢）。

---

## 三、已验证事实（带日期与判据，不要重新试探）

### 3.1 引擎（watch-skill）

- **本机安装必须带 extras**：
  `uv tool install --force --python 3.11 --with psutil --with mlx-whisper --editable ".[perceive,ocr,whisper,index]"`
  —— 缺 `perceive` 时定点抽帧直接报错，而 `doctor` 不会告诉你（2026-08-08）
- **`watch-skill` 在 PATH 里 ≠ 能干活**。判据是**能不能 import**：
  ```bash
  V=~/.local/share/uv/tools/watch-skill/bin/python
  for m in onnxruntime rapidocr faster_whisper scenedetect; do $V -c "import $m" || echo "$m 缺"; done
  ```
- **`--transcript-only` 不写索引**（实测 `list` / `search` 都找不到该视频）。
  源码依据（2026-08-28 核对）：CLI 只在 `result.perception is not None` 时才调
  `index_watch_result`，而 `--transcript-only` 恒无 perception ⇒ `--index/--no-index`
  开关在这条路径上是死的。**SKILL.md / references 里「阶段 1 是唯一索引写入点」的
  旧说法已修**（2026-08-28）：阶段 1 现按内容类型二选一——操作型走不带
  `--transcript-only` 的带索引 watch，口播型保留快路径并明示不写索引
- `fastembed` 曾缺失 ⇒ `search` 退化成纯关键词（只打印提示，不报错）。
  **2026-08-28 实测已装**（补 extras 时 index extra 带上），语义检索真实可用：
  已索引视频上中文词组命中 0.82–0.88、英文查询命中 OCR 行 0.71+（含跨语言）
- **非 CUDA 机器的 whisper 默认档是 `base`**，中文技术词错得厉害。已知台词实测（2026-08-08）：
  `base` 错 4 处（自检→字简、索引→所引、产出→传出、不验证→补验证），
  `WATCHSKILL_WHISPER_MODEL=medium` 错 1 处。**`large-v3-turbo` 在 CPU 上尚未验证**
- 日志噪音（CoreML `E5RT`、`objc[`、RapidOCR 空白帧报告）都不是错误，读输出前先 grep 掉

### 3.2 两个 agent 的能力差异（这条决定了流程怎么写）

| | Claude Code CLI | Hermes + deepseek |
|---|---|---|
| 直接读图 | ✅ `Read` 帧 | ❌ **无原生图片读取**，必须绕 `mcp__minimax__understand_image`（已实测可用：逐字读出画面三行文字、认对颜色形状） |
| 真实工具轨迹 | ✅ `--output-format stream-json` 能拿到 `tool_use` | ❌ **`-z` 的 session 不落库** ⇒ 至今无法证明它读没读那 5 张帧 |
| 触发「这视频讲了啥」 | **0 次 Skill 事件**（正确不触发；同刻正例 2 次） | **3/3 误触发** |
| 出四件套耗时 | 触发到 Skill 事件 **75s+**，负例跑到超时 | **4:15 / 6:40** |
| 认证 | 会过期（401），`auth status` 谎报 | provider 配好一直可用 |

> **SKILL.md 阶段 2 曾写「subagent 内 `Read` 每个帧路径」——
> 那句话默认了 agent 能吃图，Claude 能，Hermes 不能。已加对照表修正。**

分工建议：**开发与验证用 Claude Code CLI**（可观测、能读图），
**批量无人值守用 Hermes**（快、认证稳）。

### 3.3 Hermes 侧安装（要装到别的 profile 时照这个）

- 正确路径：`~/.hermes/profiles/<profile>/skills/<category>/<name>/SKILL.md`
  —— **少了 `<category>` 那一层认不到**；`~/.hermes/skills/` 也不行
- 用软链，不要复制
- **验证只有两条算数**：① 问 agent 自己；② `prompt-size` 的
  `skills index` 字节数做 park/restore（实测 7,921 ↔ 8,059 B，差 138）
- `hermes skills install <raw URL>` **在 v0.19.0 上不可用** —— `--help` 承诺了
  代码里没有的功能（`skills_hub.py` 安装路径里没有 URL 分支）
- Hermes agent 要求模型 **≥64K 上下文**。213 的本地 gemma 只有 16,384（`/props` 实测）
  ⇒ 那台机器上 agent 起不来，与 skill 无关

### 3.4 description 与触发

- **YAML block scalar 里不要留空行。** `skill-creator/utils.py` 的续行循环遇到
  不以两空格开头的行就停 ⇒ 空行后面 400+ 字被静默丢掉。
  Hermes 用正规 YAML 不受影响（已做插回空行的已知变化实验），
  但**换个朴素解析器就会丢半段描述**。已全部去掉空行
- description 里的排除清单**要留**（Claude 侧靠它就够），
  正文第 0 步的出口也**要留**（给触发较弱的 agent 兜底）。两者不是替代关系

### 3.5 校验与盲测

- `scripts/validate.py` **双向有分辨力**：未填充模板 12 个错误；合格笔记 0 错 0 提醒
- 已修的五个校验器 bug（都带实测依据，注释里写了原因）：
  多行 HTML 注释内的编号行被误计；非 UTF-8 / AppleDouble `._*.md` 抛 traceback；
  「引用的图片存在」在**零引用时也通过** ⇒ 已加「证据帧非空」；
  起点**倒退**时把「上一步终点 − 本步起点」当重叠量，两个不相交区间被报成
  「重叠 385s」⇒ 改为真区间相交（2026-08-28）；
  路线组织的手册（步骤按任务排序、时间戳仅作回查）被单调 ERROR 误杀
  ⇒ frontmatter `organization: task-routes` 显式声明后降为提醒（2026-08-28）
- **`validate.py` 满分 ≠ 手册可用。** 它查结构、时间戳、hash，
  **查不出你有没有读对画面**。实测：一份满分手册把
  `"triton-windows>=3.7,<3.8"` 抄成 `"<3.7"`，**约束整个反了**
- 所以操作型笔记**必做盲测**：`scripts/blind_prep.py <笔记目录> /tmp/blind`，
  然后交给一个**干净的 subagent**，禁止它上网、禁止读隔离目录外的文件

---

## 四、代码地图

| 文件 | 用途 |
|---|---|
| `.claude/skills/video-distill/SKILL.md` | **流程真源**，第 0 步是「该不该走这套流程」的出口 |
| `scripts/validate.py` | 分层校验，阶段 3 必跑。每条检查的注释里写着它为什么存在 |
| `scripts/blind_prep.py` | 盲测隔离器：只留 PLAYBOOK、移除截图嵌入与图注、打印标准提示词 |
| `scripts/trigger_test.py` | 触发准确性。`--backend hermes`（问自述，快）／`--backend claude`（读真实 `tool_use` 事件，硬）。**强制两个已知对照，不符则数据作废** |
| `evals/trigger-evals.json` | 20 条触发样例（9 正 / 11 负，负例是近似命中） |
| `evals/evals.json` | 1 条执行类评测 |
| `templates/` | NOTES / PLAYBOOK / EXTEND 三件套 |
| `references/engine-internals.md` | 引擎内部行为与实测数据。**想改 SKILL.md 任何一条规则前先读它** |
| `patches/001-apple-silicon-accel.patch` | 可选加速（mlx-whisper + RapidOCR CoreML），**非 Apple Silicon 不要打** |

---

## 五、安全与边界

- 仓库是**公开**的。写进去之前想一遍：这段内容能公开吗
- **不要把第三方内容再发布进来。** 2026-08-08 第一次发布时混进了
  `mattpocock/skills` 的 30 个 skill（无 LICENSE 无署名），已从历史移除并 force-push。
  `.gitignore` 已排除 `.agents/` 与 `skills-lock.json`，**别再解除**
- 不提交模型权重、token、`.env`；`.gitignore` **不支持行尾注释**（踩过：`tmp-vision/  # 64M` 什么也没排除）
- 克隆 URL 里带 PAT 会留在 `.git/config` —— 用 `gh auth login` 或 SSH key
