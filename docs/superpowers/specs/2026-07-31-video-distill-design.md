# video-distill 设计文档(v2,三路评审修订版)

日期:2026-07-31
状态:待用户批准
项目:`/Users/vdev/Claude/Projects/video`(独立项目,与润图项目无关)
修订说明:v2 吸收了三个评审 subagent(技术核查 / 设计评审 / 落地排查)的意见,主要变更:新增阶段 0 预探测与查重、分段观看改为 subagent 架构、中文字幕策略重写、PLAYBOOK 条件化、增加模板与校验脚本。

## 1. 目标

建立一个名为 `video-distill` 的 Claude Code skill,能够:

1. **完整理解**教学类视频(YouTube / Bilibili / 本地文件),包括图表、操作演示画面、声音、字幕等多模态内容;
2. **沉淀知识点**为结构化、带时间戳、可回查的 Obsidian 笔记,按分类组织;
3. **产出操作指导**(操作型视频),让用户不看视频、只凭文档按视频知识点操作;
4. **扩展知识**,补充视频未讲透的关联内容,与视频原文严格区分来源;
5. (可选)将方法论型内容进一步蒸馏成可调用的 Agent Skills。

## 2. 路线选择

| 路线 | 说明 | 结论 |
|------|------|------|
| A. 编排型自研 skill | 自研 SKILL.md 流程规范,编排成熟组件(claude-video 观看,cangjie-skill 可选蒸馏) | **采用** |
| B. 全自研管线 | 自己写 yt-dlp/ffmpeg/Whisper 脚本 | 否决:重复造轮子 |
| C. 纯手动组合 | 每次手动 /watch 再口头整理 | 否决:不可复现 |

## 3. 依赖组件

| 组件 | 角色 | 安装/配置 |
|------|------|------|
| claude-video(bradautomates,12.9k★) | 观看引擎:下载、抽帧、转录 | `/plugin marketplace add bradautomates/claude-video` + `/plugin install watch@claude-video` |
| ffmpeg / yt-dlp | 底层依赖 | claude-video 首次运行自动安装(**仅 macOS via brew**,需已装 Homebrew) |
| Whisper API key | 语音转录 | `GROQ_API_KEY`(优先)或 `OPENAI_API_KEY`,存 `~/.config/watch/.env`。**处理中文/B 站视频为事实必需**(见 5.1 字幕策略) |
| cangjie-skill(kangarooking,5.5k★,可选) | 方法论蒸馏 | **clone 整个仓库**到 `~/.claude/skills/cangjie-skill/`(非 plugin marketplace) |
| obsidian 技能组 | 笔记写入 vault,OFM 语法 | 已安装 |

**备选引擎备注(watch-skill,oxbshw)**:其字幕语言可经环境变量配置、内置本地 faster-whisper 免 key、有面向搜索索引的多语言 OCR/embedding。当前不采用:项目过新(2026-07 发布,245★)、技术栈重(Python 3.11+uv+服务),且其多语言优势集中在检索索引层——本方案理解靠 Claude、检索靠统一中文笔记,该层不存在;字幕方面本方案阶段 0 的逐视频动态选择比其静态全局配置更灵活。重新评估的触发条件:claude-video 的英文字幕硬编码长期不修,或无字幕视频转录费用可观(后者也可先用单独 `pip install faster-whisper` 本地转录解决,不必引入整个 watch-skill)。

**依赖冒烟测试**(实施时的前置动作):安装后用一个 1 分钟短视频实测 `--start/--end`、`--resolution`、`--detail`、`--out-dir`、`--max-frames`、`--timestamps` 各 flag,把实测命令写进 SKILL.md。(技术核查已确认这些 flag 存在于当前版本,但以实测为准。)

## 4. 目录结构

### 4.1 skill 项目(本仓库)

```
/Users/vdev/Claude/Projects/video/
├── .claude/skills/video-distill/
│   ├── SKILL.md                  # 流程规范(rigid checklist)
│   ├── templates/                # 三件套模板,Claude 填空而非自由发挥
│   │   ├── NOTES.md
│   │   ├── PLAYBOOK.md
│   │   └── EXTEND.md
│   └── scripts/
│       └── validate.py           # 产出校验脚本(约 50 行)
├── docs/superpowers/specs/
└── README.md
```

**安装方式:推荐软链到 `~/.claude/skills/video-distill` 全局可用**(本 skill 与任何代码项目无关,用户可能在任意目录触发);本仓库作为开发与版本化载体。

### 4.2 笔记存储(Obsidian vault)

默认 vault `/Users/vdev/notes`(待用户确认;本机另有 `/Users/vdev/work`、`/Users/vdev/work/oneclick/vault`)。**vault 路径首次确认后写入 skill 配置(SKILL.md 或 `~/.claude/CLAUDE.md`),之后不再每次询问。**

```
<vault>/视频笔记/
├── <分类>/                        # 复用已有分类;新分类须经用户确认
│   └── <slug>/                   # slug = 平台视频ID,如 yt-dQw4w9WgXcQ / bili-BV1xx4y1z7XX / local-<文件名hash>
│       ├── <清洗后标题>.md        # 主笔记(完整层),入口
│       ├── PLAYBOOK.md           # 操作层(条件产出,见 5.4)
│       ├── EXTEND.md             # 扩展层(默认精简模式)
│       └── assets/               # 证据性关键帧,命名 mm-ss-描述.jpg
└── 视频索引.base                  # Obsidian Bases 视图,按 frontmatter 自动聚合,零手工维护
```

**命名与链接规则**:

- 文件名清洗:替换 `/ \ : # ^ [ ] |` 等非法及破坏 wikilink 的字符,长度上限 80 字符,不含 emoji;
- 互链一律用**完整路径 wikilink**(`[[视频笔记/编程开发/yt-xxx/PLAYBOOK|操作手册]]`),因各视频目录下 PLAYBOOK/EXTEND 同名,短链接会歧义;
- 时间戳锚点为可点击链接:YouTube `&t=<秒>s`;Bilibili `?t=<秒>`,**多 P 视频需带 `p=N` 参数**;本地文件降级为纯文本 `[mm:ss]`;
- frontmatter 必填:`source`(URL 或本地路径)、`video_id`、`author`、`date`、`category`、`type`(操作型/理论型/混合)、`tags`、`duration`、`generated`(生成日期);可选 `series`(系列课程名,同系列另建一个 MOC 笔记列各集 wikilink);
- 常见坑用 callout(`> [!warning]`);写入时调用 obsidian-markdown 技能。

## 5. 处理流程(五阶段)

### 5.0 阶段 0 · 预探测与处理计划(新增,一次性用户确认点)

1. `yt-dlp` 只拉元数据(不下载):标题、作者、**时长、章节、字幕轨语言列表**、B 站分 P 信息;
2. **查重**:用平台视频 ID grep vault 内 frontmatter `video_id`,命中则问用户"更新 / 跳过 / 另存版本",**禁止静默覆盖**(重跑保护,见 5.4);
3. 分类初判(基于标题/作者/简介;先枚举 vault 现有分类目录,只能从中选或经用户确认新建);
4. 制定处理计划并**打包成一次确认**:分段数、字幕策略(原生 zh 字幕可得?走 Whisper?费用预估)、检测模式与分辨率、预计耗时(分钟级)与 token 量级、是否启用 WebSearch 扩展、**≥20 分钟的视频给出章节地图供用户选择精看范围**。

### 5.1 阶段 1 · 观看采集

**字幕策略(v2.1:按原生语言动态选择,支持任意语种)**:claude-video 硬编码只拉英文字幕(`--sub-langs "en.*"`),**非英语视频的原生字幕它一律拉不到**。因此不按语种写死分支,而是:

- 阶段 0 已获取视频语言与字幕轨语言列表,据此**逐视频动态选择**:英文视频走 claude-video 原生流程;其他语言(中/日/韩/德…)由 skill 自行 `yt-dlp --write-subs --sub-langs "<原生语言>.*" --convert-subs vtt --skip-download`(B 站按需加 `--cookies-from-browser`)取字幕;
- 优先级:人工字幕 > 平台自动生成字幕 > Whisper > 纯视觉 + 明示局限;
- Whisper 兜底天然多语言(约 100 种语言、自动语种识别),Groq/OpenAI 与本地 faster-whisper 行为一致;
- Claude 对帧内文字(任意文字系统)的识别本身是多语言的,画面理解层无需额外处理;
- **笔记输出统一中文**,术语/命令/代码保留原文,非中文视频的关键论断可附原文引述(与 5.4 语言规则一致)。

**下载与分辨率检查(v2 新增)**:B 站未登录只发 480p 以下清晰度。下载后必须检查实际分辨率,**<720p 且视频含代码/界面演示 → 停下告知用户**:提供 cookie(`--cookies-from-browser`)或本地高清文件,否则代码/界面文字转写不可信。

**采集参数**:统一 `--out-dir` 指向该视频固定工作目录(scratchpad 下 `<slug>/work/`),各分段共用,避免重复下载;默认 `--detail balanced`;界面/代码演示视频 `--resolution 1024`;Whisper 音频超 25MB(Groq 单文件上限)→ ffmpeg 切块重试。

### 5.2 阶段 2 · 分段理解(v2 架构重写:subagent 承担)

**单会话逐段观看不成立**:40 分钟视频 4 段 @1024px ≈ 19-31 万 token 图片,第 2 段就会触发上下文压缩,后段等于在残影上工作。因此:

- 超过 10 分钟的视频分段(每段 ≤10 分钟),**每段派一个 subagent**:子代理内调用 /watch(帧只进入子代理上下文,用完即弃),按转写规则产出**纯文本段落笔记**,连同该段选中的关键帧路径一起返回;
- 每个子代理的 prompt 携带前段的 running summary(术语表 + 进行中的主题),保证段间指代连贯;
- **每段笔记立即落盘**到 `<slug>/work/.drafts/segment-N.md`(含覆盖时间范围)。SKILL.md 开头规定断点续跑:先查 `.drafts/` 已有哪几段,只补缺失段;
- 每段完成向用户输出一行进度;
- **关键帧同步拷贝**:段落笔记落盘的同时,把该段证据帧 cp 到 vault `assets/`(命名 `mm-ss-描述.jpg`)——不等到最后,防止与临时目录清理竞态。

**转写规则**(子代理执行):

- 图表 → 数据表或 Mermaid,记录轴、数值、结论;
- 操作画面 → 可复现步骤(菜单路径、点击对象、输入值、预期反馈);
- 代码画面 → 完整转写代码文本;**帧内文字辨认不清必须写 `[画面文字不可读 @mm:ss]`,禁止猜测补全**;
- 讲解/字幕 → 时间戳对齐要点。

### 5.3 阶段 2.5 · 类型判定(v2 新增)

全部段落完成后,主代理判定视频类型并记入 frontmatter `type`:

- **操作型**:有可复现的软件/工具操作 → 产出 PLAYBOOK;
- **理论型**:讲原理、观点、方法论,无具体操作 → **不产出 PLAYBOOK**(避免为满足结构而编造步骤),以"要点卡 + 自测题"小节并入主笔记;
- **混合型**:PLAYBOOK 只覆盖实际演示的部分。

短视频(<10 分钟且知识点少)允许三层合并为单文件,不建目录三件套。

### 5.4 阶段 3 · 沉淀写入(Obsidian)

1. 基于实际内容**最终确认分类与标题**(与阶段 0 初判不符时此处修正,连同 slug/是否覆盖一并向用户确认——这是第二个也是最后一个确认点);
2. 用 `templates/` 模板填空生成主笔记 /(条件)PLAYBOOK / EXTEND,合并各段草稿,检查段间术语与编号一致;
3. EXTEND 默认精简模式(Claude 自身知识 + 官方文档链接);WebSearch 仅当阶段 0 用户勾选;所有扩展内容标注 `[扩展]`,与带时间戳的视频原文严格分离;
4. 笔记语言:正文中文,术语/命令/代码保留原文,首次出现给中译;
5. **重跑保护**:目标文件已存在且 `generated` 后被人工改动过(mtime 晚于 generated 或 git diff 非空)→ 写 `*.regen.md` 并列出差异由用户裁决,禁止直接覆盖;
6. 写入后**必须运行 `scripts/validate.py`** 并贴出结果:检查 frontmatter 必填字段齐全、每条知识点以时间戳链接开头(证据规则的机械化)、产出文件与类型判定一致、assets 引用的图片存在;
7. 最终回复逐项自报 checklist 完成状态。

### 5.5 阶段 4 · 可选精华蒸馏

- 输入是**阶段 1 保留的原始转录文本**(work dir 中的 transcript),不是蒸馏后的笔记——cangjie 的三重验证需要"原文至少 2 处独立佐证",总结性笔记会让验证失效。因此 **transcript 必须随产出存档**(拷入 `<slug>/work/` 保留或 vault 内 `transcript.md`),清理 work dir 前先确认蒸馏意向;
- 方法论型 → cangjie-skill 蒸馏为技能包;操作型 → PLAYBOOK 直接固化为项目内 skill;
- 默认不执行,处理完成后由用户决定。

**清理时序**:关键帧已拷 assets、transcript 已存档、用户无追加问题 → 才允许清理 work dir。

## 6. 质量控制

1. **证据规则**:每个知识点必须有语音或画面证据并附时间戳;辨认不清必须标注 `[画面文字不可读]`,禁止猜测(validate.py 校验时间戳格式);
2. **可复现盲测**(操作型视频):派一个只读 PLAYBOOK(不给转录和帧)的 subagent 复述操作、列缺失信息;缺口用焦点模式回看补齐——**回看也走 subagent 且带 `--max-frames 15`**,防止二次 token 雪崩;
3. **机械保障**:模板锁定结构 + validate.py 校验 + checklist 自报,不依赖纯提示词自觉;
4. **降级透明**:任何降级(无字幕、纯视觉、低清晰度、跳段)记入 frontmatter 与文首信息块。

## 7. 错误处理

| 场景 | 处理 |
|------|------|
| 非英语原生字幕无法经 claude-video 拉取 | skill 自行 yt-dlp 按阶段 0 探测到的原生语言拉字幕;失败走 Whisper(多语言自动识别) |
| 无字幕且无 Whisper key | 纯视觉理解,明示"转录缺失";讲解为主的视频建议直接暂停并提示配 key(或本地 faster-whisper) |
| B 站未登录清晰度 <720p 且含代码/界面 | 暂停,请用户提供 cookie 或本地文件 |
| B 站需登录/地区限制 | 提示用户提供本地文件,不绕过 |
| Whisper 音频 >25MB(Groq 上限) | ffmpeg 切块分段转录 |
| 视频 ≥20 分钟 | 阶段 0 出章节地图,用户选精看范围 |
| 会话中断 | `.drafts/` 断点续跑,只补缺失段 |
| 帧文字不可读 | `--resolution 1024` + 焦点模式重抽该段(subagent) |

## 8. 使用方式与首次体验

**Preflight 清单**(SKILL.md 第一步,一次性检查):插件已装?ffmpeg/yt-dlp 在?key 在 `~/.config/watch/.env`?vault 路径已固化?README 明示"首次使用预计 10 分钟准备时间"。

```
> 用 video-distill 把这个视频沉淀成笔记:https://www.bilibili.com/video/BVxxxx
# 阶段0:元数据+查重+计划报价 → 用户确认一次
# 阶段1-2:分段 subagent 观看,逐段落盘+进度提示
# 阶段3:分类/覆盖最终确认一次 → 写入 vault + validate
# 之后可追加:
> 把 PLAYBOOK 固化成 skill / 用 cangjie-skill 蒸馏方法论
```

**触发词设计**:description 用差异化意图词并写明负触发——"当用户要把教学视频**整理成笔记 / 沉淀到 Obsidian / 做成操作手册 / 蒸馏知识**时使用;本 skill 编排 claude-video 完成观看;单纯询问视频内容、无需沉淀笔记时不适用(那是 claude-video 的场景)"。

## 9. 非目标(YAGNI)

- 不做跨视频全库语义检索(笔记本身可被 Grep/Bases 检索);
- 不做自动批量播放列表处理(系列课程仅预留 `series` frontmatter + MOC 约定);
- 不绕过任何平台的登录/版权限制。

## 10. 实施范围

实现物:

1. `.claude/skills/video-distill/SKILL.md`(核心流程规范,含 preflight、五阶段、subagent 编排、Obsidian 规范);
2. `templates/` 三件套模板;
3. `scripts/validate.py`(约 50 行校验脚本);
4. `README.md`(安装步骤含两条 plugin 命令、key 配置、首次使用预期);
5. vault 内 `视频笔记/` 目录约定与 `视频索引.base`。

前置动作:安装 claude-video 插件(两条命令)+ 依赖冒烟测试(1 分钟短视频实测各 flag)+ 确认目标 vault。验收 = 用一个真实中文教学视频(B 站)+ 一个英文操作教学视频(YouTube)各跑通全流程,validate.py 通过,检查产出符合 4.2 / 5 / 6 节要求。
