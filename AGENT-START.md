# 给 agent 的自助安装单

**你是另一台机器上的 agent，要把「视频→笔记」这套能力装到本机。**
照下面做。每步都带**验证方法** —— 装完不验证，等于没装。

仓库：`https://github.com/vinsunfeng/learning-video-skills`

---

## 0. 先想清楚你要装哪一半

这套东西有两层，**可以只装一层**：

| 层 | 是什么 | 不装它会怎样 |
|---|---|---|
| **skill（编排层）** | `SKILL.md` + 模板 + 校验脚本，**纯文本** | 没有流程规范，你得自己想怎么做笔记 |
| **watch-skill（观看引擎）** | 转录 / OCR / 抽帧的 CLI，**要装依赖和模型** | 看不了视频，skill 无从下手 |

**先装 skill，再装引擎。** 因为 skill 里写着引擎该怎么用 ——
反过来装，你会不知道装的东西要拿来干什么。

---

## 1. 拿到东西：三条路，按你要做什么选

仓库是**公开**的，不需要凭证（2026-08-08 实测匿名 200）。
**两条可用**（路 C 曾写在这里，实测不可用，已标注）。

### 路 A：只想先看要装什么（不落盘）

```bash
curl -sL https://raw.githubusercontent.com/vinsunfeng/learning-video-skills/main/AGENT-START.md
```

### 路 B：要真跑起来 —— `git clone`（推荐）

```bash
REPO=~/learning-video-skills
git clone https://github.com/vinsunfeng/learning-video-skills.git "$REPO"
```

**验证**：`ls "$REPO/.claude/skills/video-distill/SKILL.md"` —— 文件在才算拉到。
体积约 1.1 MB（2026-08-08 实测），几秒钟。

### ~~路 C：一条命令装进 Hermes~~ —— **实测不可用，别走**

```bash
# ❌ hermes -p <profile> skills install <raw SKILL.md URL> --category note-taking --yes
```

`hermes skills install --help` 明写「or a direct HTTP(S) URL to a SKILL.md file」，
**但 v0.19.0 的代码里没有这个分支。** 2026-08-08 三条独立证据：

| 试的东西 | 结果 |
|---|---|
| 本仓库的 raw URL（同机 `curl` = **200**） | `Could not fetch ... from any source` |
| 换第三方非隐藏目录的公开 SKILL.md | **一样失败** ⇒ 不是 `.claude` 点目录的问题 |
| 去掉全部代理变量重试 | **一样失败** ⇒ 不是代理 |
| `grep urlparse\|startswith("http")` 于 `skills_hub.py` 的安装路径 | **没有** ⇒ 代码里确实没这个分支 |

> **`--help` 承诺了代码里没有的功能，而我照着 `--help` 把它写进了文档。**
> 这是「凭印象写接口」的变体，而且更难防 ——
> **官方帮助文本也是一种二手信息。**

⇒ **只走路 B。** 装 skill 靠 clone + 软链（下一节）。

仓库里**故意没有**的东西（别去找）：

- `vendor/` —— watch-skill 的源码副本。**同一份代码存两处必然漂移**，
  所以让你自己装（见第 3 步）
- 模型权重、`tmp-*`、workspace 产物 —— 几十 MB 到几 GB，
  **可以重新下载，而 git 历史不能**

---

## 2. 装 skill

### 2a. 装给 Claude（Claude Code / Cowork）

```bash
mkdir -p ~/.claude/skills
ln -sfn "$REPO/.claude/skills/video-distill" ~/.claude/skills/video-distill
```

**验证**：新开一个会话，问「你有 video-distill 这个 skill 吗」。
（诚实声明：Claude 侧**没有**不依赖 LLM 的验证判据——Hermes 的判据二
`prompt-size` park/restore 在 Claude 这边没有等价物，且 `claude auth status`
会谎报。LLM 不可用的机器上，只能验到「软链存在且目标可读」为止，
这是已知的不对称，不是你能修的缺陷。）

### 2b. 装给 Hermes agent

**路径必须带 `<category>` 那一层**，少了就认不到：

```bash
PROFILE=<name>        # 你的 profile 名（hermes profile create <name> 创建）
CATEGORY=note-taking  # 见 ls ~/.hermes/profiles/$PROFILE/skills/（create 会预建分类目录）

ln -sfn "$REPO/.claude/skills/video-distill" \
        ~/.hermes/profiles/$PROFILE/skills/$CATEGORY/video-distill
```

**验证 —— 只有这一个判据算数：直接问 agent 自己**

```bash
hermes -p $PROFILE -z '你的 skills 里有没有 video-distill？
有就一句话说它干什么，没有只回「没有」。' --yolo
```

它答「有」并说对用途 ⇒ 成功。

> ### ⚠️ 两个错法（都实测踩过）
>
> | 错法 | 后果 |
> |---|---|
> | 放 `~/.hermes/skills/<name>/` | **agent 认不到**（那是 builtin 的位置） |
> | 少了 `<category>` 那一层 | 同上 |
>
> ### ⚠️ 不要用这两个命令验证
>
> - **`hermes skills list`** —— 它只列**注册表来源**（builtin / official）的
>   skill，**本地软链进去的不出现**。我用它验过，得到「没装上」的错误结论，
>   而真相是我在看错的地方。
> - **`hermes prompt-size` 的 "Skills by size" 列表** —— 同样漏本地 skill。
>   **但它的 `skills index` 那个数看得见** —— 见下面的判据二。
>   我曾因为列表瞎就把整个工具否掉了：
>   **同一个工具里可以有两个仪器，一个瞎一个不瞎。**
>
> **量错地方，会得到一个干净的、完全错误的答案。**

### 判据二（不需要 LLM，机器上没配模型也能用）

**如果上面那条跑不起来，用这个。**

```bash
hermes -p $PROFILE prompt-size | grep "skills index"   # 记下数字
mv ~/.hermes/profiles/$PROFILE/skills/$CATEGORY/video-distill $HOME/vd-parked
hermes -p $PROFILE prompt-size | grep "skills index"   # 应当变小
mv $HOME/vd-parked ~/.hermes/profiles/$PROFILE/skills/$CATEGORY/video-distill
hermes -p $PROFILE prompt-size | grep "skills index"   # 应当精确回到原值
```

2026-08-08 在 Fedora 机器上实测：**7,921 → 8,059 B（+138），拿掉即回落**。

> 这不是「看一眼数字对不对」，是**拿一个已知变化考仪器** ——
> 数字跟着软链动，才说明它真看见了。

### ⚠️ 判据一跑不起来时，先看错误说的是什么

```
agent failed: Model ... has a context window of 16,384 tokens,
which is below the minimum 64,000 required by Hermes Agent.
```

或 `No LLM provider configured`，或（2026-09-08 实测新增）：

```
agent failed: No usable credentials found for provider 'deepseek'. Set DEEPSEEK_API_KEY.
```

**三条都跟 skill 一点关系没有** —— 前两条是模型上下文/provider 没配；
第三条是**新建 profile 的 `.env` 是空模板，凭证不继承**（2026-09-08 实测），
复制一个能跑的 profile 的 `.env` 即可：

```bash
cp ~/.hermes/profiles/<能跑的profile>/.env ~/.hermes/profiles/$PROFILE/.env
```

**别把它们读成「装失败了」**，改用判据二。视觉模型也要单独配
（新 profile 默认没有 `auxiliary.vision`，做法与实测可用的模型名见
[`HERMES-INSTALL.md`](./HERMES-INSTALL.md) §〇），配完拿一张已知内容的帧
考它——「能读图」以仪器检查为准，不以 agent 自述为准。

### 2c. 成本：装 skill 是要付常驻费的

```bash
hermes -p $PROFILE prompt-size | grep "skills index"
```

- **`skills index` 是常驻的** —— 每次调用都付（本机实测约 7 KB）
- **`SKILL.md` 只在被触发时才读** —— 一次性

所以：通用 skill 装十几个没问题；但**给延迟敏感的 profile 装无关 skill 是纯亏**。
装完看一眼这个数，别凭感觉。

---

## 3. 装 watch-skill 观看引擎

**先装它，再自检。** 原来这一节只写了「跑 doctor」，
却没说 `watch-skill` 这个命令从哪来 —— **那是一条悬空的指令**。

```bash
uv tool install --python 3.11 "watch-skill[perceive,ocr,whisper,index]"
watch-skill doctor    # 它会说缺什么，并**自动补** deno / ffmpeg / yt-dlp
                      # （deno/yt-dlp 自补有 Fedora 实测；裸 Fedora 的 ffmpeg 自补无记录，
                      #  装不上就先 `dnf install ffmpeg`（RPM Fusion）再跑 doctor）
```

> ⚠️ **`watch-skill` 在 PATH 里，不等于它能干活。**
> 2026-08-08 在一台「已经有 watch-skill」的机器上实测：
> `onnxruntime` / `rapidocr` / `faster_whisper` **三个全缺** ——
> 裸装的版本没有 OCR、没有转录，只是命令存在。
>
> **判断装没装，别看 `command -v`，要看能不能 import：**
>
> ```bash
> V=~/.local/share/uv/tools/watch-skill/bin/python
> for m in onnxruntime rapidocr faster_whisper; do $V -c "import $m" || echo "$m 缺"; done
> ```
>
> 上面那条 `uv tool install` **不会因为「已经装过」就跳过 extras**（已实测补齐）。
> 所以：**照跑一次，不要因为命令已存在就略过这一步。**

**钉 3.11，不要用系统 Python**，也**不要用 watch-skill 自带的**
`curl install.sh | sh`（它会挑系统 Python；uv 官方安装脚本无此问题，
uv 本体没装就 `curl -LsSf https://astral.sh/uv/install.sh | sh`）。
理由见 `README.md`：这套栈全是二进制轮子，`onnxruntime` 是硬门槛。

**Apple Silicon 想要加速**（转录走 GPU、OCR 走 CoreML）：

```bash
git clone https://github.com/oxbshw/watch-skill.git /tmp/watch-skill
cd /tmp/watch-skill && git checkout -b local-patches
git apply --check "$REPO/patches/001-apple-silicon-accel.patch"   # 先干跑
git apply         "$REPO/patches/001-apple-silicon-accel.patch"
uv tool install --force --python 3.11 --with psutil --with mlx-whisper --editable "$PWD"
```

**补丁是可选加速，不打也能跑**；非 Apple Silicon 不要打。
2026-08-08 对上游最新版实测 `git apply --check` **通过**。

> **「装过了」这件事必须能被检查** ——
> 否则每个新会话都要重装一遍才敢用。

### ⚠️ 非 Apple 机器：**默认模型会把中文技术词听错**

`transcribe/local.py` 只有检测到 **CUDA** 才用 `large-v3`，
否则落到 **`base`**。2026-08-08 在 213（CPU）用一段**已知台词**实测：

| 我说的 | `base` 听成 |
|---|---|
| 环境**自检** | 环境**字简** |
| **索引**起来 | **所引**起来 |
| **产出**笔记 | **传出**笔记 |
| **不**验证 | **补**验证 |

四个错的全是**技术词** —— 而技术视频的笔记恰恰靠这些词。

```bash
export WATCHSKILL_WHISPER_MODEL=large-v3-turbo   # 或 medium，看机器扛不扛
```

> 转录「跑通了」和转录「能用」是两件事。
> **只看它有没有输出，会把一份错字连篇的转录当成成功。**

### macOS 上值得知道的两处（本机实测）

| 项 | 说明 |
|---|---|
| 转录 | 装 `mlx-whisper` 后端明显更快（Apple Silicon） |
| OCR | RapidOCR 开 CoreML 后明显更快 |

细节见 `README.md` 与 `docs/`。

---

## 4. 装完之后

读 `.claude/skills/video-distill/SKILL.md` —— 那是**流程真源**，
不要凭这份安装单去猜它怎么工作。

**换机器部署，先本地化 SKILL.md「固化配置」里的两行**（2026-09-08 标注）：
`WATCH_SKILL_BIN`（用 `command -v watch-skill` 查实际位置）和 `VAULT`
（你的 Obsidian 笔记库，不存在就先建 `视频笔记/` 子目录）。这是全文档
仅有的两处本机路径，其余命令都引用变量——改这两行即可。
skill 的三个验收脚本只用 Python 标准库，任何 3.11+ 环境直接能跑；
引擎在非 Apple 机器上不打补丁也能跑（代价见第 3 步的模型档位说明）。

产出是三件套：带时间戳的主笔记、可脱离视频复现的 PLAYBOOK、
与视频原文严格分离的扩展阅读。

---

## 5. 检查表

装任何一层，四步，缺一步就算没装：

1. **放对位置** —— Hermes 的 skill 要带 `<category>` 层
2. **用软链** —— 别让同一份东西存在两个副本
3. **问 agent 自己验** —— 不看 `skills list`，不看 `prompt-size`
4. **记下 index 成本** —— `prompt-size` 的 `skills index` 那一行

> **先找仪器，再下结论。**
> 而找到仪器之后还要多问一句：**这个仪器看得到我要找的东西吗？**
> `hermes skills list` 是个好仪器 —— 但它看不见本地 skill。
