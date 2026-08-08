# 在另一台机器上真装一次：2026-08-08 于 192.168.3.213

**为什么要做这件事**：之前只验到「文件可读、补丁可打」。
那两条成立，**不等于另一台机器照文档能装成** ——
我验的是文档的可读性，不是文档的可执行性。

机器：Fedora Linux 44 / x86_64（**不是 Apple Silicon** ——
正好考那条「非 Apple Silicon 直接从上游装」的路径）。

## 一、结果

| 步骤 | 结果 |
|---|---|
| `git clone`（匿名） | ✅ 1.1 MB |
| skill 软链进 Hermes profile | ✅ |
| **`prompt-size` 看见它** | ✅ 7,921 → **8,059 B**（+138），拿掉即回落 |
| watch-skill extras 补齐 | ✅ onnxruntime / rapidocr / faster_whisper |
| `doctor` 自动补 deno | ✅ 装到 `~/.watch-skill/bin/deno` |
| **端到端 OCR** | ✅ 造一个画面写 `HELLO 213 OCR` 的片子，**原样认出** |
| 「问 agent 自己」验证 | ❌ **在这台机器上跑不起来**（见下） |

## 二、四个只有真装一次才会暴露的问题

### 1. 我把「列表瞎」过度概括成了「prompt-size 不能用」

原文写着「也不要只看 `hermes prompt-size`」。**这句话错了一半。**

- `Skills by size` **那个列表**确实看不见本地 skill —— 这半是对的
- `skills index` **那个数**看得见 —— 而我把它一起否掉了

实测（park / restore 已知对照）：

```
装着     skills index : 8,059 B
拿掉软链 skills index : 7,921 B      ← 差 138 B
装回去   skills index : 8,059 B      ← 精确回到原值
```

> **同一个工具里可以有两个仪器，一个瞎一个不瞎。**
> 而我因为其中一个瞎，把另一个也扔了。

这条现在很重要，因为 ——

### 2. 「问 agent 自己」是我给的**唯一**判据，而它在这台机器上不可用

```
hermes -z: agent failed: Model ...gemma-4-26B... has a context window of
16,384 tokens, which is below the minimum 64,000 required by Hermes Agent.
```

换云端模型：`No LLM provider configured`。

**所以这台机器上没有任何办法照原文档验证。**
而一个照文档做的 agent 会看到上面那条报错 ——
它一个字都没提 skill，**却极易被读成「装失败了」**。

> **只有一种验证方式、且那种方式依赖 LLM 的文档，在半数机器上无法验证。**

⇒ 已加入不依赖 LLM 的判据（上面第 1 条）。

### 3. `watch-skill` 在 PATH 里 ≠ 它能干活

这台机器**本来就有** `watch-skill v1.0.0`。而：

```
onnxruntime  缺   rapidocr  缺   faster_whisper  缺
```

裸装的 watch-skill **没有 OCR、没有转录**，只是命令存在。
照文档原样跑那条 `uv tool install ... "watch-skill[perceive,ocr,whisper,index]"`
**确实补齐了**（三个都变 OK，Python 钉在 3.11.14）——
uv 不会因为「已经装过」就跳过 extras。**这条是好消息，且现在是实测的。**

> 判断装没装，不要看 `command -v`，要看**能不能 import**。

### 4. 体积写错了

文档写 880 KB，加了 `patches/` 之后实际 **1.1 MB**。小事，但
**一个连体积都对不上的文档，会让人怀疑其它数字**。

## 三、第二轮：全面审计（同日，逐条可执行检查）

第一轮只走了「照文档装一遍」。第二轮把**每一条声明变成一个检查**。
又抓出 **6 个**，其中 3 个是我写错的、1 个是我自己代码的 bug、
2 个是我的**检查手段**本身有病。

### 3.1 路 C（`skills install <URL>`）**根本不可用** —— 我照 `--help` 抄的

`hermes skills install --help` 明写「or a direct HTTP(S) URL to a SKILL.md file」。
实测 v0.19.0：

| 试的东西 | 结果 |
|---|---|
| 本仓库 raw URL（**213 自己 curl = 200**） | `Could not fetch ... from any source` |
| 第三方非隐藏路径的公开 SKILL.md | **一样失败** ⇒ 不是 `.claude` 点目录 |
| 去掉全部代理变量 | **一样失败** ⇒ 不是代理 |
| `skills_hub.py` 安装路径里 grep URL 分支 | **没有** ⇒ 代码里确实没这功能 |

> **`--help` 承诺了代码里没有的功能，而我照着它写进了文档。**
> **官方帮助文本也是二手信息** —— 抄它等于凭印象写接口。

### 3.2 转录能跑 ≠ 转录能用（已知台词 A/B）

造一段 TTS **已知台词**（13.8s）：

| | 环境**自检** | **索引**起来 | **产出**笔记 | **不**验证 | 错数 |
|---|---|---|---|---|---|
| `base`（非 CUDA 默认档） | 环境**字简** | **所引** | **传出** | **补**验证 | **4** |
| `WATCHSKILL_WHISPER_MODEL=medium` | ✓ | **锁引** | ✓ | ✓ | **1** |

日志 `model=medium device=cpu (int8)` 是「处理已施加」的证据 ——
**先证明自变量动了，再读因变量。**

`transcribe/local.py` 只在检测到 **CUDA** 时才用 `large-v3`，否则落 `base`。
四个错的全是**技术词**，而技术视频的笔记恰恰靠这些词。

> **只看它有没有输出，会把一份错字连篇的转录当成成功。**

### 3.3 `validate.py` 的 bug：docstring 承诺了代码没做的事

`bullet_lines` 的 docstring 写着「跳过注释」，而代码只跳过**以 `<!--` 开头的那一行** ——
多行注释的内部行会漏进来。而 `EXTEND.md` 模板自带的注释里正好有编号列表
⇒ **任何保留模板注释的笔记都被误判不通过**。

修完两个方向都复验：注释行不再被计数（6 条 → 4 条），
未填充模板仍被拒（11 个错误）。

> 和 3.1 是**同一个形状，而这次是我自己的代码。**

### 3.4 校验器两个方向都有分辨力（这次是好消息）

| 输入 | 结果 |
|---|---|
| 未填充的模板目录 | **不通过：12 个错误** —— 且每条都具体（占位符、缺 `transcript.md`、图片失效、hash 不符） |
| 逐项补齐的合格笔记 | **通过：0 错误 0 提醒** |

中途 12 → 4 → 2 → 0，每一步都是我的样本在变好。
**只会拒的校验器和只会放行的校验器一样没用。**

### 3.5 三处文档不一致（都会让远程 agent 走死）

| 位置 | 问题 |
|---|---|
| `HERMES-INSTALL` 的验证命令 | 用 `~/.local/bin/<profile>` —— **那是我这台机器的启动器约定**，别的机器没有 |
| 同上 | 硬编码 `-m deepseek-v4-flash`，213 上报 `No LLM provider configured` |
| `README` 的软链 | `ln -s "$PWD/..."` 假设 cwd 是仓库，且 `-s` 在链接已存在时失败；已统一为 `ln -sfn "$REPO/..."` |

另外 `HERMES-INSTALL` 拿 `player-a`（扑克 profile）当例子，与本仓库主题无关，已改 `<profile>`。

### 3.6 我的两个检查手段本身是坏的

1. **链接审计的过滤器太粗** —— 把模板占位符 `{{URL}}`、示例 `url&t=83s`
   全报成坏链接。**用错的过滤器检查，第 N 次。**
2. **`pgrep -af "watch-skill watch"` 匹配到了我自己的 ssh 命令行** ⇒
   连续几次读到「仍在跑」，而**什么都没在跑**；
   紧接着 `pkill -f` 同样自匹配，**把自己的 shell 杀了**。

> **一个会匹配到自己的过滤器，报出的永远是自己。**
> 这次它没造成错误结论，纯属运气 —— 我差点把别的进程当成自己的任务进度。

### 3.7 顺带清掉的历史问题：公开仓库里混着别人的 skill

第一次发布时把 **30 个**第三方 skill（来自 `mattpocock/skills`，见当时的
`skills-lock.json`）一起推上了公开仓库 —— 400K / 77 文件，
**比 video-distill 本体（68K / 37 文件）还大**，且仓库无 LICENSE、无署名。

已从 HEAD 移除并**重写历史**；已认证 API 复核旧 commit：
`No commit found for SHA` ⇒ 真的不在了（`raw` 亦 404）。
本地文件 **78 个逐一对齐**恢复，一个不差。

（我先前说「31 个」——**那个数是我数错的**，实为 30。）

> 顺带记一次事故：`git filter-branch` 结尾会 `reset --hard`，
> **把工作区里那些文件一起删了**。
> 幸而 `&&` 链在 `ls` 失败处断掉，`gc --prune` 与 force-push 都没执行，
> 才从 `refs/original` 完整取回。
> **删之前先想清楚「哪一步之后就不可逆了」。**

## 四、诚实的未验证项（不写成「通过」）

- ~~转录未验证~~ —— **已验**，见 3.2。但 `large-v3-turbo` 档在 CPU 上没测
  （`medium` 已跑数分钟），**只验到 `medium`**。
- **`sentence_transformers` 不在**，但 `doctor` 报 `index healthy`。
  可能检索走的是别的后端。**没查清之前不写「坏了」** ——
  上一次我就是把「我没看到」写成了「它不存在」。
- 213 的 Hermes **agent 本身**跑不起来（无 provider + 本地模型 16K < 64K），
  所以「**skill 被触发后 agent 能不能正确走完流程**」在这台机器上**没验** ——
  这是目前最大的缺口：验到的是「装得上、引擎能干活、校验器能判」，
  **不是「agent 用它产出的笔记是好的」**。
- **正向校验样本是我用脚本拼的，不是 agent 生成的。**
  它证明校验器会放行合格笔记，**不证明真实流程会产出合格笔记**。
- `sentence_transformers` 不在而 `doctor` 报 `index healthy` —— 仍未查清。
- 端到端只跑过**我自己造的 13.8s 片子**，没跑过真实教学视频
  （长视频的分段、场景切分、多轮检索都没碰）。
