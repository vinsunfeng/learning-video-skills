---
name: video-distill
description: |
  把教学类视频（YouTube / Bilibili / 本地文件）沉淀成结构化、带时间戳、可回查的
  Obsidian 笔记与操作手册。只要用户提到把视频「整理成笔记 / 沉淀下来 / 记到 Obsidian /
  写成操作手册 / 做成文档 / 蒸馏知识点 / 看完做个总结存起来」，或者丢来一个教程、课程、
  技术分享、软件演示视频并希望留下可复用的产物，就使用本 skill —— 即使他们没说出
  「笔记」这个词。产出是分层的三件套：带时间戳的主笔记、可脱离视频复现的 PLAYBOOK、
  与视频原文严格分离的扩展阅读。
  不适用：用户只想知道视频讲了什么、问某个片段发生了什么、要个口头摘要而不需要落盘 ——
  那种情况直接调 watch-skill CLI 回答，不要走本流程。
---

# video-distill

把教学视频变成「不看视频、只凭文档就能复现」的知识资产。

这是一份操作清单。每条规则背后都有源码核对和实测支撑，**看起来多余想精简某一条之前，
先读 `references/engine-internals.md` 对应小节** —— 有几条（索引清空、静默付费、
字幕轨误选）不遵守不会报错，只会安静地产出坏数据。

---

## 固化配置

```bash
WATCH_SKILL_BIN=/Users/vdev/.local/bin/watch-skill   # 绝对路径：subagent 的 PATH 不保证含 ~/.local/bin
VAULT=/Users/vdev/notes                              # 已确认，支持 Bases
NOTES_ROOT="$VAULT/视频笔记"
```

**所有 watch-skill 调用用这个包装形式，不要精简：**

```bash
env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u GEMINI_API_KEY -u OPENROUTER_API_KEY \
    WATCHSKILL_SUBTITLE_LANGS='zh.*' \
    WATCHSKILL_WHISPER_MODEL=large-v3-turbo \
    WATCHSKILL_CLOUD_STT_ENABLED=false \
    WATCHSKILL_COST_POLICY=offline_only \
    "$WATCH_SKILL_BIN" <subcommand> ...
```

| 项 | 不加会怎样 |
|---|---|
| `env -u ...KEY` | 带索引的 watch 会用 Haiku 描述最多 24 帧且**不检查 cost_policy**，有 key 就静默付费 |
| `SUBTITLE_LANGS='zh.*'`（不带 en） | 多数视频 info.json 的 `language` 为 None，字幕轨按字母序回落，`media.en.vtt` 会压过 `media.zh.vtt`，拿机翻轨当原文 |
| `WHISPER_MODEL` 显式指定 | 内存探测失败会落到 `base`，中文错字密集（「多参考图」→「多餐口圖」），不能用于笔记 |

英文视频临时改 `WATCHSKILL_SUBTITLE_LANGS='en.*'`。详见 references 第 2、3、5 节。

---

## 机械契约（写入前必读）

正文怎么组织、小节怎么起名、行文风格 —— **这些你自己判断，按内容实际结构来写更好**，
不要被模板的示例小节束缚。第一版实测就是这样：自创的 11 个小节比模板示例贴合得多。

但有 6 处是**字面契约**：`validate.py` 按精确形式 grep 它们，写法不同就过不了闸门。
它们的存在不是为了统一风格，是为了让「这份笔记可回查、来源可分辨」这件事**可机器验证**——
否则质量只能靠人逐份读。

| 契约 | 精确形式 | 为什么必须是这个形式 |
|---|---|---|
| 时间戳锚点 | **markdown 链接**：`[01:23](url&t=83s)`，区间也可以 `[02:38–02:51](url&t=158s)` | 可点击跳回原片是「这句话是讲者说的」的凭据。`〔02:38–02:51〕` 全角括号不是链接，点不动，等于没有凭据 |
| 主笔记锚点小节 | 必须有一个 `## 视频要点`，其下每条以时间戳链接开头 | 这是唯一被逐条校验的小节。**你可以自由增加任意其他小节**（背景、结构、坑…），只要这一节存在 |
| PLAYBOOK 步骤 | 每个 `### ` 步骤块内出现至少一个时间戳链接 | 操作手册最易错的是顺序和参数值，跳回原片是唯一纠错手段 |
| EXTEND 条目 | 每条以 `- ` 开头的条目里出现字面串 `[扩展]` | 这个标记是给机器读的。文件开头声明「本文件是扩展层」对人足够，但校验器只能逐条看。少了它，视频原文和补充内容在机器眼里无法区分 |
| `engine_video_id` | frontmatter 必填，16 位十六进制，且**必须等于 `sha256(source.strip())[:16]`** | 事后 `ask` / `search` 全靠它。校验器会用同一份 frontmatter 里的 `source` 重算并比对 —— 填个占位串过不了闸 |
| `content_hash` | frontmatter 必填 = **frontmatter 之后的正文，`.strip()` 后 sha256 十六进制前 16 位** | 重跑保护靠它判断文件是否被人工改过。算法不一致就永远误报「被改过」，保护机制自我失效。只对正文取 hash，否则 hash 会自指 |

```python
# content_hash 的唯一正确算法
import hashlib
body = 文件内容[frontmatter 结束的 "---\n" 之后 :]
content_hash = hashlib.sha256(body.strip().encode("utf-8")).hexdigest()[:16]
```

阶段 3 跑完 `validate.py` 就能确认这 6 条，且**每条都是真检查而非存在性检查**：
`engine_video_id` 用 `source` 重算比对，`content_hash` 重算比对（不一致是 ERROR，
不是提醒 —— 刚写完就对不上只可能是算错了），时间戳锚定行首，`[扩展]` 与小节名逐条 grep。

**闸门不过就不算交付完成**，不要贴着错误清单说「内容质量很好」——内容好和可验证是两件事，
这份 skill 要的是两者都有。

---

## Preflight（会话内首次运行做一遍）

```bash
"$WATCH_SKILL_BIN" doctor
```

`python`(3.11.x) / `ffmpeg` / `yt-dlp` / `js-runtime`(deno，YouTube 需要) 必须 ok。
`memory: warn` 可忽略（doctor 自身探测的 cosmetic 问题）。失败就停下报告，不要降级硬跑。

---

## 阶段 0 · 预探测与计划（第一个确认点）

1. **元数据**：`yt-dlp --skip-download --dump-single-json` 取 title / uploader /
   duration / `language` / `subtitles` / `automatic_captions` / `chapters` / 源分辨率。
2. **查重**：用平台 video_id grep `$NOTES_ROOT` 下的 frontmatter。命中就问
   「更新 / 跳过 / 另存版本」，不要静默覆盖 —— 用户可能已经手工补充过内容。
3. **分类初判**：`ls "$NOTES_ROOT"` 枚举现有分类，从中选；要新建就问一次。
   `$NOTES_ROOT` 为空（首次使用）时没有可选项 —— 这时**直接提出一个分类名**放进阶段 0
   的那次确认里，不要因为「只能从现有里选」而卡住。这条规则的目的是防止分类无节制增殖，
   不是在空目录上制造死锁。
4. **清晰度预判**：源高于 720p 且含代码/界面演示 → 此处就告诉用户「引擎硬编码
   `height<=720` 且不接受 cookie，要看清代码请给本地高清文件」。等下载完才发现会白费一次下载。
5. **打包成一次确认**：字幕来源、分段方案、抽帧分辨率、预计耗时、是否启用 WebSearch 扩展。
   ≥20 分钟且有章节 → 给章节地图让用户选精看范围。
   转录耗时按 RTF 0.05x 估；不要报「转录费用」，本地转录免费。

---

## 阶段 1 · 全片转录（唯一的索引写入点）

```bash
env -u ... "$WATCH_SKILL_BIN" watch "<source>" --transcript-only --out-dir "$WORK"
```

**这里不加 `--no-index`。** 引擎的 `video_id = sha256(source)` 与时间范围无关，而写索引
前会 `DELETE` 该 video_id 的所有派生行 —— 所以后续任何带索引的 watch 都会把这次成果清空。
详见 references 第 1 节。

完成后：

- 核对字幕轨确实是原生语言（看 `media.*.vtt` 的语言后缀与内容）。不符就显式设
  `WATCHSKILL_SUBTITLE_LANGS` 重跑。不要用机翻英文轨当原文——它是翻译，不是讲者说的话。
- 转录存档到 `$WORK/transcript.md`（阶段 4 蒸馏的前提，清理 work dir 后不可恢复）。
- **取 `engine_video_id`**。它不出现在 watch 的输出里（早期版本的 SKILL.md 说去找
  `Indexed: <id>` 那行 —— 那行不存在，实测 grep 不到）。自己算：

  ```bash
  python3 -c "import hashlib,sys;print(hashlib.sha256(sys.argv[1].strip().encode()).hexdigest()[:16])" "<source 原样字符串>"
  ```

  必须和你传给 watch 的 source 字符串**逐字节一致**（引擎就是 `sha256(source.strip())[:16]`，
  URL 少一个参数就是另一个 id）。用 `"$WATCH_SKILL_BIN" list` 交叉核对一下。
  这个值是六条机械契约之一：不落盘、work dir 一清，事后 `ask` / `search` 就只能重跑整条流水线。

---

## 阶段 2 · cue 定位 + 定点抽帧 + 分段理解

### 2.1 生成 cue 时间戳表

对索引做语义检索，命中的 hits 自带时间戳：

```bash
env -u ... "$WATCH_SKILL_BIN" search "操作步骤 点击设置 菜单路径"
env -u ... "$WATCH_SKILL_BIN" ask <engine_video_id> "代码示例 终端命令 报错信息"
```

**中文查询写成「空格分隔的、3 字以上词组」**：

```
✗ "如何配置代理服务器超时"
✓ "代理服务器 超时配置 网络设置"
```

引擎的 `_fts_query` 和 `lexical_anchor` 都按空白切分，且后者丢弃长度 < 3 的词。
中文整句会退化成一条要求逐字相邻的短语查（几乎零命中），同时把置信度锚点压成 0，
导致升级阶梯过度触发、白耗算力。所以双字词并成四字：`超时配置`、`环境变量`、`常见错误`。
详见 references 第 4 节。

**同一语义也试一遍英文词组。** 实测同一视频上英文查询命中率 **0.72 vs 中文 0.34** ——
原因不在模型偏好，在于索引里有大量英文：界面标签、节点名、参数名、文件名，以及不少
教学视频带的中英双语硬字幕（OCR 会把两条都读进索引）。嵌入模型本身是跨语言的
（实测中↔英余弦 0.59），所以 `LoRA loader node`、`resolution selector`、`API key setup`
这类查询往往比中文词组更能命中界面演示的时刻。**两种都发一遍，合并 hits。**

辅以转录里的指示语（「你看这里 / 打开设置 / 输入这个 / 如图 / 注意」）与章节边界。
索引不可用时降级为纯指示语匹配，记入 `degradations`。

**读输出前先过滤日志噪音**，否则帧路径和 OCR 文本会被冲没：

```bash
... | grep -v -e E5RT -e '^objc\[' -e RapidOCR
```

三个来源分别是 CoreML EP（本地补丁 2 的副作用）、cv2 与 av 各带一份 libavdevice、
以及 RapidOCR 对空白帧的例行报告。都不是错误。

### 2.2 分段观看

分段判据是**信息密度，不是时长**。实测一个 13.7 分钟的界面演示视频抽出 88 帧、
83 个场景切换 —— 按时长它「不用分段」，按实际负载它必须分。看这几个信号：

- 阶段 1 的 watch 报告里场景数 / 帧数（>60 帧就该分）
- cue 表的规模（cue 多到超过 `--max-frames` 就必须分）
- 内容形态：界面演示、逐节点讲解、代码走查 → 密；口播、幻灯片朗读 → 疏

分段就按 10~12 分钟切，每段派一个 subagent；密度低且总时长短才单遍处理。

```bash
env -u ... "$WATCH_SKILL_BIN" watch "<source>" \
  --start <t0> --end <t1> \
  --timestamps <该段 cue，逗号分隔> \
  --resolution 1280 --max-frames 60 --no-index --out-dir "$WORK"
```

- **必须加 `--no-index`**（理由同阶段 1）。
- **cue 数 ≤ `--max-frames`**：引擎对 cues 做 `_even_sample(cues, cap)`，超量会被抽稀，
  等于白定位，而且不报错。cue 多就提高 max-frames 或缩短分段。
> ### ⚠️ 你可能读不了图 —— 先确认，再决定怎么读帧
>
> 下面写的 `Read` 每个帧路径，**前提是你能直接接收图片输入**（Claude 可以）。
> **Hermes 不能** —— 2026-08-08 实测它自述「内置工具列表里没有图片分析工具」，
> 必须绕一个视觉 MCP。
>
> 后果是实测出来的：Hermes 跑完 29 分钟教程，产出通过校验的四件套，
> 而 `assets/` **0 张证据帧** —— 它跳过了整个抽帧阶段。
> **不是它没有视觉能力，是这份 skill 假设了它有 `Read` 图片的能力。**
>
> | 你的情况 | 怎么读帧 |
> |---|---|
> | 能直接吃图（Claude） | `Read` 帧路径 |
> | 不能（Hermes 等） | 用视觉 MCP，如 `mcp__minimax__understand_image`（已实测可用：逐字读出画面三行文字、认对颜色与形状） |
> | 两者都没有 | **必须写进 frontmatter 的 `degradations`**，并且不要产出操作型 PLAYBOOK —— 纯字幕的步骤不可复现 |
>
> **抽帧本身不需要任何 key** —— OCR 是本地 RapidOCR。
> 缺 key 只影响引擎的「场景描述」（`scene descriptions skipped (vision.no_api_key)`），
> 而**画面文字照样读得到**。别把「没有视觉模型」误当成「不能抽帧」。

- subagent 内 `Read` 每个帧路径（帧只进子代理上下文，用完即弃），返回**纯文本段落笔记**
  加该段证据帧路径。prompt 带上前一段的 running summary（术语表 + 进行中的主题），
  否则段间指代会断。
- 段落笔记**立刻落盘** `$WORK/.drafts/segment-N.md`，注明覆盖的时间范围。
- 证据帧**同步** `cp` 到 vault 的 `assets/`（命名 `mm-ss-描述.jpg`），不要攒到最后——
  会和临时目录清理产生竞态。
- 每段完成给用户一行进度。

**断点续跑**：开工前先看 `$WORK/.drafts/` 有哪几段，只补缺失的。

### 2.3 转写规则

| 画面类型 | 转写成 |
|---|---|
| 图表 | 数据表或 Mermaid，保留轴、单位、数值、结论 |
| 操作演示 | 可复现步骤：菜单路径、点击对象、输入值、预期反馈 |
| 代码/终端 | 完整文本 |
| 讲解/字幕 | 时间戳对齐的要点 |

**专有名词、命令、参数值以 OCR 为准。** 这是实测结论：同一批帧上 OCR 正确读出
「多参考图」「真人 AI 短剧」，而 whisper 写成「多餐口圖」「真人短距」。换成
large-v3-turbo 后同音词「短距/短剧」依然错 —— 声学模型解决不了同音，画面文字才是
专名的可靠来源。

- OCR 有该词就用 OCR 的写法，冲突处标 `[OCR 与转录不一致 @mm:ss]`；
- OCR 未覆盖才采信转录；
- 两者都不可辨 → 走免模型回补：`ask <engine_video_id> "<画面文字 具体内容>"`，
  引擎会自动 `dense_resample`（高分辨率密集重抽 + OCR）→ `crop_and_reocr`（按 OCR box
  裁剪 2× 放大重读），两步都不调模型，恢复的证据还会 merge 回索引。

  **对它的正确预期**：它经常回答「视频没有清楚显示」，而这**就是它的价值** ——
  把「我读不出来」升级成「已确认视频里确实没有」。前者是你的失误，后者是一条有据可查的
  边界，可以放心写进「未覆盖 / 存疑」。别指望它总能变出答案，指望它帮你区分这两种情况。
- 仍不可辨才写 `[画面文字不可读 @mm:ss]`。不要猜测补全 —— 一个编造的参数值会让整份
  手册失去可信度。

OCR 自己也会错（「拆解」→「折解」、「剧本」→「刷本」），两者是互补关系。有疑问时
以你自己读帧所见为最终裁决。

---

### 2.4 盲测（操作型必做，不是可选的质量加分）

写完 PLAYBOOK **就做这一步**，不要留到最后。派一个 subagent，只给它 PLAYBOOK
（不给转录、不给帧），让它复述操作并列出卡住的地方。

实测这一步在一份看起来完整的手册里揪出 3 处硬伤，包括「验证」小节里一条基于算术错误的
诊断公式（`10×24+1=241`，而实际 `frame_count` 是 65），会把读者引向去改 fps ——
正是手册本身明令禁止的操作。这类错误你自己读不出来，因为你知道视频里是怎么做的；
盲测代理不知道，所以它会卡住，而卡住的地方就是缺口。

缺口回补优先 `ask <engine_video_id> "<缺口词组>"`；`ask` 解决不了才定点重抽。

**完成判据**：盲测代理能一路走到最后一步，剩下的疑问全部落在「未覆盖 / 存疑」小节里。

---

## 阶段 2.5 · 类型判定

| type | 判据 | 产出 |
|---|---|---|
| 操作型 | 有可复现的软件/工具操作 | 产出 PLAYBOOK |
| 理论型 | 只讲原理、观点、方法论 | **不产出 PLAYBOOK**，改为「要点卡 + 自测题」并入主笔记 |
| 混合 | 兼有 | PLAYBOOK 只覆盖实际演示的部分 |

不要为了凑齐三件套而编造操作步骤 —— validate.py 会检查 type 与实际产出一致。

短视频（<10 分钟且知识点少）允许三层合并为单文件，不建目录三件套。

---

## 阶段 3 · 写入 Obsidian（第二个确认点）

### 目录与命名

```
$NOTES_ROOT/<分类>/<slug>/
├── <清洗后标题>.md      # 主笔记，入口
├── PLAYBOOK.md          # 条件产出
├── EXTEND.md
├── transcript.md
└── assets/              # mm-ss-描述.jpg
```

- `slug`：`yt-<视频ID>` / `bili-<BV号>` / `local-<文件名hash>`（可读，与引擎 id 不同）
- 文件名清洗：替换 `/ \ : # ^ [ ] |`，上限 80 字符，不含 emoji
- 互链用**完整路径 wikilink**：`[[视频笔记/编程开发/yt-xxx/PLAYBOOK|操作手册]]` ——
  各视频目录下 PLAYBOOK/EXTEND 同名，短链接会指向错的文件
- 时间戳锚点：YouTube `&t=<秒>s`；Bilibili `?t=<秒>`（多 P 加 `p=N`）；本地文件降级为
  纯文本 `[mm:ss]`

### 步骤

1. 基于实际内容最终确认分类与标题（与阶段 0 初判不符就在此修正），连同 slug、
   是否覆盖一并确认。这是最后一个计划内确认点。
2. 用 `templates/` 三件套填空，合并各段草稿，检查段间术语与编号一致，拷入 `transcript.md`。
3. EXTEND 默认精简模式（自身知识 + 官方文档链接）；WebSearch 仅在阶段 0 勾选时启用。
   扩展内容一律标 `[扩展]`，且不带时间戳 —— 时间戳是「视频里说过」的凭据，混进扩展层
   就分不清哪些话是讲者说的了。
4. 语言：正文中文，术语/命令/代码保留原文，首次出现给中译；非中文视频的关键论断附原文引述。
5. **重跑保护**：写入时把正文 hash 存进 frontmatter `content_hash`。重跑时重算，
   不一致即视为被人工改过 → 写 `*.regen.md` 列出差异交用户裁决，不要直接覆盖。
   （不要用 mtime 判断，Obsidian 插件会改 mtime。）
6. **运行校验并贴出结果**：
   ```bash
   python3 <skill_dir>/scripts/validate.py "<笔记目录>"
   ```
   有 ERROR 就修到通过再交付；WARN 逐条说明为何可接受。
7. 逐项自报 checklist 完成状态。

---

## 阶段 4 · 可选蒸馏（默认不执行）

处理完成后由用户决定：

- **方法论型** → cangjie-skill 蒸馏成技能包。输入必须是 `transcript.md` **原始转录**，
  不是笔记 —— cangjie 的三重验证要求「原文至少 2 处独立佐证」，总结性笔记会让验证失效。
- **操作型** → PLAYBOOK 固化为项目内 skill。

**清理时序**：证据帧已拷 assets、transcript 已存档、用户无追加问题 → 才允许清理
`$WORK`。引擎自己的下载缓存由 LRU 管理，不要手动删。

---

## 质量控制

1. **证据规则**：每条视频知识点必须有语音或画面证据并附时间戳；辨认不清必须标注。
2. **可复现盲测**：见阶段 2.4 —— 操作型视频的必做步骤，不在这里重复。
3. **降级透明**：任何降级写进 frontmatter `degradations` 与文首信息块 —— 字幕缺失走
   whisper、纯视觉、源被降采样到 720p、跳段、OCR 关闭、索引不可用。

---

## 错误处理

| 场景 | 处理 |
|---|---|
| 拿到机翻英文轨 | 核对 info.json `language`，重跑并显式指定原生语种 |
| 完全无字幕 | 本地 mlx whisper（无 key、无体积上限）。这是常态而非异常 |
| 源 >720p 且含代码/界面 | 阶段 0 就要本地高清文件。**没有 cookie 方案，引擎硬性不支持** |
| 需登录 / 地区限制 | 提示提供本地文件，不绕过 |
| 帧文字不可读 | OCR 交叉校验 → `ask` 免模型回补 → 定点重抽 → 仍不可读则标注 |
| 会话中断 | `.drafts/` 断点续跑，只补缺失段 |
| mlx 权重缺失 | 回退 `WATCHSKILL_WHISPER_MODEL=medium WATCHSKILL_WHISPER_BACKEND=ctranslate2`，记入 degradations |
| 引擎异常 | 记录复现命令；必要时按 README 的退路切回 claude-video |

---

## 典型调用

```
用 video-distill 把这个视频沉淀成笔记：https://www.bilibili.com/video/BVxxxx
```

阶段 0 确认一次 → 阶段 1 全片转录（13 分钟视频约 40 秒）→ 阶段 2 cue 定位 + 定点抽帧
→ 阶段 3 确认一次后写入 + 校验。

计划内确认 2 次；查重命中、需新建分类、需本地高清文件会各追加一次，最坏约 5 次。

---

## 附带资源

- `templates/NOTES.md` · `templates/PLAYBOOK.md` · `templates/EXTEND.md` — 产出模板，填空用
- `scripts/validate.py` — 分层校验，阶段 3 必跑
- `references/engine-internals.md` — 引擎内部行为与实测数据。想改动上面任何一条规则前先读它
