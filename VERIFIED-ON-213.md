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

## 三、诚实的未验证项（不写成「通过」）

- **转录**：测试片是 ffmpeg 生成的纯画面，**没有音轨**。
  它报「no whisper rung succeeded」—— 而无音轨本来就该失败。
  **这个失败什么也不能证明**，转录在 213 上仍属未验证。
- **`sentence_transformers` 不在**，但 `doctor` 报 `index healthy`。
  可能检索走的是别的后端。**没查清之前不写「坏了」** ——
  上一次我就是把「我没看到」写成了「它不存在」。
- 213 的 Hermes **agent 本身**跑不起来，所以
  「skill 被触发后能不能正确执行流程」在这台机器上没验。
