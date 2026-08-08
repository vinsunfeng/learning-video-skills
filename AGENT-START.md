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

## 1. 拉仓库

```bash
git clone https://github.com/vinsunfeng/learning-video-skills.git ~/learning-video-skills
```

**验证**：`ls ~/learning-video-skills/.claude/skills/video-distill/SKILL.md`
—— 文件在，才算拉到了。

仓库里**故意没有**的东西（别去找）：

- `vendor/` —— watch-skill 的源码副本。**同一份代码存两处必然漂移**，
  所以让你自己装（见第 3 步）
- 模型权重、`tmp-*`、workspace 产物 —— 几十 MB 到几 GB，
  **可以重新下载，而 git 历史不能**

---

## 2. 装 skill

### 2a. 装给 Claude（Claude Code / Cowork）

```bash
ln -sfn ~/learning-video-skills/.claude/skills/video-distill \
        ~/.claude/skills/video-distill
```

**验证**：新开一个会话，问「你有 video-distill 这个 skill 吗」。

### 2b. 装给 Hermes agent

**路径必须带 `<category>` 那一层**，少了就认不到：

```bash
PROFILE=wiki          # 换成你的 profile 名
CATEGORY=note-taking  # 见 ls ~/.hermes/profiles/$PROFILE/skills/

ln -sfn ~/learning-video-skills/.claude/skills/video-distill \
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
> - **`hermes prompt-size`** 的 "Skills by size" —— 同样漏本地 skill。
>
> **量错地方，会得到一个干净的、完全错误的答案。**

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

`SKILL.md` 里写清了它需要什么。**别假设环境干净，先自检**：

```bash
watch-skill doctor
```

它会说缺什么（`ffmpeg` / `yt-dlp` / `deno` / 模型权重）。**缺了再装。**

> **「装过了」这件事必须能被检查** ——
> 否则每个新会话都要重装一遍才敢用。

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
