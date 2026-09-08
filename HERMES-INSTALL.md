# 把能力装进 Hermes agent：给 agent 自己看的操作手册

这份文档是给**另一个 agent** 读的。照做就行，每步都带**验证方法** ——
装完不验证，等于没装。

## 〇、新建 profile 时：凭证不继承（2026-09-08 实测）

`hermes profile create <name>` 生成全套目录，但 **`.env` 只有 3 行空模板**——
不继承全局 `~/.hermes/.env`，也不继承其他 profile 的凭证。此时问 agent 会报：

```
hermes -z: agent failed: No usable credentials found for provider 'deepseek'. Set DEEPSEEK_API_KEY.
```

**这跟 skill 毫无关系，别读成「装失败了」。** 修法二选一：

```bash
cp ~/.hermes/profiles/<能跑的profile>/.env ~/.hermes/profiles/<name>/.env   # 快路径
hermes -p <name> setup                                                     # 自己配
```

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
ln -sfn "$SRC" ~/.hermes/profiles/<profile>/skills/note-taking/video-distill
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
hermes -p <profile> -z '你的 skills 里有没有 <skill-name>？
有就一句话说它干什么，没有只回「没有」。' --yolo
```

（原来这里写的是 `~/.local/bin/<profile>` —— 那是**我这台机器上的启动器约定**，
别的机器没有；也别硬编码 `-m deepseek-v4-flash`，
2026-08-08 在 213 上它报 `No LLM provider configured`。）

它答「有」并说对用途 ⇒ 成功。

**不要用 `hermes skills list` 验证** —— 它只列注册表来源
（`builtin` / `official`）的 skill，**本地放进去的不出现**。
2026-08-08 我用它验过，得到「没装上」的错误结论，
而真相是**我在看错的地方**。

**`hermes prompt-size` 的 "Skills by size" 列表也漏本地 skill** ——
但**它的 `skills index` 那个数看得见**。我曾因为列表瞎就把整个工具否掉：

> **同一个工具里可以有两个仪器，一个瞎一个不瞎。**

### 判据二：不需要 LLM（当 agent 起不来时用这个）

```bash
hermes -p $P prompt-size | grep "skills index"    # 记下
mv <软链> /tmp/vd-parked
hermes -p $P prompt-size | grep "skills index"    # 应当变小
mv /tmp/vd-parked <软链>                          # 应当精确回到原值
```

2026-08-08 Fedora 机器实测：**7,921 → 8,059 B（+138），拿掉即回落**。
**拿已知变化考仪器**，数字跟着软链动才算它真看见了。

### ⚠️ 判据一起不来时，先看错误说什么

```
agent failed: Model ... context window of 16,384 tokens,
below the minimum 64,000 required by Hermes Agent.
```

或 `No LLM provider configured`。**这两条跟 skill 无关** ——
Hermes agent 要求模型 **≥64K 上下文**。别读成「装失败了」，改用判据二。

> **量错地方，会得到一个干净的、完全错误的答案。**
> 而**只有一种验证方式、且它依赖 LLM 的文档，在半数机器上无法验证。**

## 二、`hermes skills install` 的真实约束

```
hermes skills install <identifier>
  identifier = 注册表标识符（如 openai/skills/skill-creator）
             | 指向 SKILL.md 的 HTTP(S) URL
  --category CATEGORY   装进哪个分类目录
  --name NAME           覆盖名字（URL 的 SKILL.md 没有 name: 时需要）
```

**它不接受本地路径。** 所以本地 skill 只能软链/复制进去（见上）。

### ⚠️ 上面那段「URL」是抄 `--help` 的，**实测不可用**

v0.19.0 上 `skills install <raw URL>` 一律
`Could not fetch ... from any source`，即使同机 `curl` 返回 **200**。
换第三方非隐藏路径的 URL 同样失败；无代理；
而 `skills_hub.py` 的安装路径里**根本没有 URL 分支**。

> **`--help` 承诺了代码里没有的功能** ——
> 官方帮助文本也是二手信息，**照抄它等于凭印象写接口**。

⇒ 让别人装上的唯一可靠方式：**clone 仓库 + 软链**。

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
