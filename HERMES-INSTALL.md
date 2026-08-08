# 把能力装进 Hermes agent：给 agent 自己看的操作手册

这份文档是给**另一个 agent** 读的。照做就行，每步都带**验证方法** ——
装完不验证，等于没装。

## 一、装 skill：路径必须带 category 层

### ✅ 正确

```
~/.hermes/profiles/<profile>/skills/<category>/<skill-name>/SKILL.md
```

`<category>` 是现有分类目录之一（`ls ~/.hermes/profiles/<profile>/skills/` 可见）：
`apple` `autonomous-ai-agents` `creative` `email` `github` `media` `mlops`
`note-taking` `productivity` `research` `smart-home` `social-media`
`software-development`

软链（推荐）或复制：

```bash
# REPO = 你 clone 下来的位置
REPO=~/learning-video-skills
SRC=$REPO/.claude/skills/video-distill
ln -sfn "$SRC" ~/.hermes/profiles/player-a/skills/note-taking/video-distill
```

**用软链，不要复制。** 同一份规则存在两个副本，副本一定会漂移，
而漂移的那一刻没人会知道。

### ❌ 两个已实测的错法

| 错法 | 后果 |
|---|---|
| 放 `~/.hermes/skills/<name>/` | **agent 认不到**（那是 builtin/bundled 的位置） |
| 少了 `<category>` 那一层 | 同上 |

### 验证：只有一个判据算数 —— 问 agent 自己

```bash
~/.local/bin/<profile> -z '你的 skills 里有没有 <skill-name>？
有就一句话说它干什么，没有只回「没有」。' --yolo -m deepseek-v4-flash
```

它答「有」并说对用途 ⇒ 成功。

**不要用 `hermes skills list` 验证** —— 它只列注册表来源
（`builtin` / `official`）的 skill，**本地放进去的不出现**。
2026-08-08 我用它验过，得到「没装上」的错误结论，
而真相是**我在看错的地方**。

**也不要只看 `hermes prompt-size`** —— 它的 "Skills by size" 也漏本地 skill。

> **量错地方，会得到一个干净的、完全错误的答案。**

## 二、`hermes skills install` 的真实约束

```
hermes skills install <identifier>
  identifier = 注册表标识符（如 openai/skills/skill-creator）
             | 指向 SKILL.md 的 HTTP(S) URL
  --category CATEGORY   装进哪个分类目录
  --name NAME           覆盖名字（URL 的 SKILL.md 没有 name: 时需要）
```

**它不接受本地路径。** 所以本地 skill 只能软链/复制进去（见上）。
若要让别人一条命令装上，把 `SKILL.md` 放到一个可访问的 HTTP(S) 地址，
然后 `hermes skills install <url> --category <cat>`。

## 三、skill 的格式：Claude 与 Hermes 通用

同一个 `SKILL.md` 两边都能用，不需要转换：

```markdown
---
name: video-distill
description: |
  一段话说清「什么时候该用它」。写触发场景，不写功能清单 ——
  agent 是靠这段话决定要不要读正文的。
---

# 正文：怎么做

...
```

同目录可放 `references/` `scripts/` `templates/` `evals/`，
正文里用相对路径引用。

**Claude 侧的软链位置**（对照）：

```bash
ln -sfn "$SRC" ~/.claude/skills/video-distill
```

## 四、装完的成本（要算，不要装了就忘）

`hermes prompt-size` 会报：

```
skills index : 7,185 B   ← **每次调用都付**，装一个 skill 多几十字节
Skills by size:
  <name>   SKILL.md 大小   index 成本
```

- **index 是常驻的**（所有调用都付）
- **`SKILL.md` 只在被触发时才读**（一次性）

所以装十几个通用 skill 是可接受的；装几十个就要看
`skills index` 那一行涨到多少。**这个数是可测的，不要凭感觉。**

## 五、装嵌入模型 / 依赖脚本

skill 需要的外部依赖（模型权重、CLI 工具）**不要塞进 skill 目录**，
而是在 `SKILL.md` 里写清「怎么检查、怎么装」，让 agent 自己确认环境。

范式（`video-distill` 就是这么做的）：

```markdown
## 环境自检（先跑这个，缺了再装）

    watch-skill doctor       # 检查 ffmpeg / yt-dlp / deno / 模型权重

缺什么它会说。**装之前先跑一次，不要假设环境干净。**
```

理由：模型权重几个 GB，进 git 会毁掉仓库；而
**「装过了」这件事必须能被检查**，否则每个新会话都要重装一遍才敢用。

## 六、给 agent 的检查表

装任何东西，四步，缺一步就算没装：

1. **放对位置** —— skill 要带 `<category>` 层
2. **用软链** —— 别让同一份东西存在两个副本
3. **问 agent 自己验** —— 不看 `skills list`，不看 `prompt-size`
4. **记下 index 成本** —— `prompt-size` 的 `skills index` 那一行

> **先找仪器，再下结论。**
> 而找到仪器之后还要多问一句：**这个仪器看得到我要找的东西吗？**
> `skills list` 是个好仪器 —— 但它看不见本地 skill。
