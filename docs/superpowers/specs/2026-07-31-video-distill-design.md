# video-distill 设计文档

日期:2026-07-31
状态:待用户批准
项目:`/Users/vdev/Claude/Projects/video`(独立项目,与润图项目无关)

## 1. 目标

建立一个名为 `video-distill` 的 Claude Code skill,能够:

1. **完整理解**教学类视频(YouTube / Bilibili / 本地文件),包括图表、操作演示画面、声音、字幕等多模态内容;
2. **沉淀知识点**为结构化、带时间戳、可回查的笔记;
3. **产出操作指导**,让用户可以不看视频、只凭文档按视频知识点操作;
4. **扩展知识**,补充视频没讲透的关联内容,且与视频原文严格区分来源;
5. (可选)将方法论型内容进一步蒸馏成可调用的 Agent Skills。

## 2. 路线选择

| 路线 | 说明 | 结论 |
|------|------|------|
| A. 编排型自研 skill | 自研 SKILL.md 流程规范,编排成熟组件(claude-video 负责观看,cangjie-skill 可选蒸馏) | **采用** |
| B. 全自研管线 | 自己写 yt-dlp/ffmpeg/Whisper 脚本 | 否决:重复造轮子,维护成本高 |
| C. 纯手动组合 | 每次手动 /watch 再口头整理 | 否决:流程不可复现,产出格式不稳定 |

## 3. 依赖组件

| 组件 | 角色 | 来源 |
|------|------|------|
| claude-video(bradautomates,12.9k★) | 观看引擎:下载、抽帧、转录 | `/plugin marketplace add bradautomates/claude-video` |
| ffmpeg / yt-dlp | claude-video 的底层依赖,首次运行自动安装 | brew |
| Groq 或 OpenAI API key(可选) | 无原生字幕时的 Whisper 转录 | 用户提供 |
| cangjie-skill(kangarooking,5.5k★,可选) | 方法论内容的精华蒸馏 | 按需安装 |
| obsidian 技能组(obsidian-markdown / obsidian-cli) | 笔记写入 Obsidian vault,使用 OFM 语法 | 已安装 |

## 4. 目录结构

### 4.1 skill 项目(本仓库)

```
/Users/vdev/Claude/Projects/video/
├── .claude/
│   └── skills/
│       └── video-distill/
│           └── SKILL.md          # skill 本体(流程规范,rigid checklist)
├── docs/superpowers/specs/       # 设计文档
└── README.md                     # 项目说明与使用方式
```

skill 放在项目 `.claude/skills/` 内随 git 版本化;在本项目目录运行 Claude Code 即可触发。如需全局可用,软链到 `~/.claude/skills/video-distill`。

### 4.2 笔记存储(Obsidian vault)

笔记不存在 skill 项目里,统一写入 Obsidian vault(默认 `/Users/vdev/notes`,本机另有 `/Users/vdev/work` 与 `/Users/vdev/work/oneclick/vault` 两个 vault,以用户确认为准),**按视频分类组织**:

```
<vault>/视频笔记/
├── <分类>/                        # 如:编程开发 / AI·机器学习 / 设计 / 运维部署 / 产品运营 / 其他
│   └── <视频slug>/               # slug = YYYY-MM-DD-标题缩写
│       ├── 📄 <视频标题>.md       # 主笔记 = NOTES(完整层),入口文件
│       ├── PLAYBOOK.md           # 操作层
│       ├── EXTEND.md             # 扩展层
│       └── assets/               # 证据性关键帧截图
└── 视频索引.md                    # 全库索引:分类 → 视频列表(wikilink)
```

分类由 Claude 根据视频内容判定并在处理开始时向用户确认;分类集合不写死,vault 中已有同名分类目录则复用。

**Obsidian 规范**(写入时调用 obsidian-markdown 技能):
- 每个文件带 frontmatter properties:`source`(视频 URL)、`author`、`date`、`category`、`tags`、`duration`;
- 主笔记、PLAYBOOK、EXTEND 之间用 wikilink 互链;主笔记加入 `视频索引.md`;
- 时间戳锚点写成可点击的视频跳转链接(YouTube `&t=`、Bilibili `?t=` 参数);
- 注意事项/常见坑使用 callout 语法(`> [!warning]` 等)。

## 5. 处理流程(SKILL.md 中的 rigid checklist)

### 阶段 1 · 观看采集(委托 claude-video)

- 输入:YouTube / Bilibili URL 或本地文件路径。
- 字幕策略:原生字幕/CC 优先(免费);无字幕走 Whisper(Groq 优先,OpenAI 备选);两者皆无 → 降级为纯视觉理解并在产出中明示局限。
- 抽帧策略:默认 `--detail balanced`(场景变化检测);**含界面操作/代码演示的视频强制 `--resolution 1024`** 保证屏幕文字可读。
- 长视频规则:**超过 10 分钟必须分段**(`--start/--end`,每段 ≤10 分钟)逐段观看,防止帧密度被稀释;各段笔记最后合并。
- Bilibili 需登录的视频:提示用户提供本地文件,不尝试绕过。

### 阶段 2 · 结构化理解

Claude 多模态通读(帧 + 带时间戳转录),产出增强时间轴笔记。分元素转写规则:

- **图表** → 转写为数据表或 Mermaid 图,记录轴、数值、结论,不允许只写"有一张图";
- **操作画面** → 可复现步骤:菜单路径、点击对象、输入值、预期反馈;关键界面帧存入 `assets/`;
- **代码画面** → 完整转写代码文本(而非截图引用);
- **讲解声音/字幕** → 时间戳对齐的要点。

### 阶段 3 · 三层沉淀(核心产出,写入 Obsidian vault)

处理开始时先确定分类(复用 vault 已有分类目录,新分类向用户确认),然后按 4.2 节结构写入:

| 文件 | 定位 | 内容要求 |
|------|------|----------|
| `<视频标题>.md`(主笔记) | 完整层 | 全部知识点,按视频章节组织,每条带时间戳锚点(可点击跳转到视频对应时刻),frontmatter 记录元信息 |
| PLAYBOOK.md | 操作层 | step-by-step 手册:前置条件 → 每一步(动作 + 预期结果)→ 常见坑(callout);用户不看视频即可照做 |
| EXTEND.md | 扩展层 | 视频未讲透的关联知识、官方文档链接、进阶方向;由 Claude 自身知识 + 按需 WebSearch 补充 |

写入完成后更新 `视频索引.md`,追加该视频的 wikilink 条目。视频元信息(URL、作者、时长、处理参数、降级记录)记入主笔记 frontmatter 与文首信息块,不再单设 SOURCE.md。

**来源标注规则(强制)**:EXTEND.md 及任何 AI 补充内容必须标注 `[扩展]`,视频原文内容标注时间戳;两者不得混排在同一条目内。

### 阶段 4 · 可选精华蒸馏

- **方法论型**内容(设计原则、架构思想、工作流)→ 喂给 cangjie-skill,蒸馏为技能包(INDEX + 多个 SKILL.md + 测试集);
- **操作型**内容 → 不走 cangjie(其三重验证会滤掉操作细节),直接把 PLAYBOOK 固化为项目内 skill,触发词设为对应操作场景;
- 该阶段默认不执行,由用户在处理完成后决定。

## 6. 质量控制

1. **证据规则**:每个知识点必须有语音或画面证据并附时间戳,禁止凭空归纳;
2. **可复现自检**:PLAYBOOK 完成后,Claude 自查"不看视频、只凭本文档能否完成操作?"——缺信息则用 claude-video 焦点模式(`--start/--end`)回看对应时间段补齐;
3. **合并一致性**:分段处理的长视频,合并时检查段间知识点编号、术语一致;
4. **降级透明**:任何降级(无字幕、纯视觉、跳段)必须记入主笔记 frontmatter 与文首信息块。

## 7. 错误处理

| 场景 | 处理 |
|------|------|
| 无字幕且无 Whisper key | 纯视觉理解,产出中明示"转录缺失"局限 |
| B 站需登录 / 地区限制 | 提示用户下载后提供本地文件 |
| 超长视频(>60 分钟) | 先产出章节地图,与用户确认精看哪些段落 |
| 帧中文字不可读 | 用 `--resolution 1024` + 焦点模式重抽该时间段 |

## 8. 使用方式(预期)

```
# 在 /Users/vdev/Claude/Projects/video 下运行 Claude Code
> 用 video-distill 处理 https://www.youtube.com/watch?v=xxxx
# 产出写入 Obsidian:<vault>/视频笔记/<分类>/<slug>/ 三件套 + 索引更新;之后可追加:
> 把这个视频的 PLAYBOOK 固化成 skill
> 用 cangjie-skill 蒸馏这个视频的方法论
```

## 9. 非目标(YAGNI)

- 不做跨视频全库语义检索(watch-skill 的领域,项目太新暂不引入;笔记本身可被 Grep/Claude 检索);
- 不做自动批量播放列表处理(先跑通单视频,有需要再加);
- 不绕过任何平台的登录/版权限制。

## 10. 实施范围

本 spec 的实现物只有三样:

1. `.claude/skills/video-distill/SKILL.md`(核心,承载全部流程规范,含 Obsidian 写入规范);
2. `README.md`(项目说明、依赖安装步骤);
3. Obsidian vault 中的 `视频笔记/` 目录约定与 `视频索引.md`(由 SKILL.md 定义,无需代码)。

前置动作:安装 claude-video 插件;确认目标 vault。无自研代码,无测试套件需求;验收方式 = 用一个真实教学视频跑通全流程,检查 Obsidian 中三件套产出与索引是否符合第 4.2、5、6 节要求。
