# watch-skill 引擎内部行为speedrun

读这份文件的时机：SKILL.md 的某条规则看起来多余、想精简它、或者行为与预期不符需要排查时。
每一条都来自源码核对 + 在这台机器上的实测，不是猜测。

基线版本：`oxbshw/watch-skill` @ `bf177b0`（2026-07-12），本地补丁分支 `local-patches`
以 `uv tool install --editable` 装入（本机开发时放在 `vendor/watch-skill`；别的机器按 `patches/README.md` 自己 clone 到任意位置）。

## 目录

- [1. 索引写入会删除旧数据](#1-索引写入会删除旧数据)
- [2. 带索引的 watch 会静默调用云端视觉](#2-带索引的-watch-会静默调用云端视觉)
- [3. 字幕轨按字母序回落](#3-字幕轨按字母序回落)
- [4. 中文检索的缺陷在查询侧](#4-中文检索的缺陷在查询侧)
- [5. whisper 档位与 Apple Silicon](#5-whisper-档位与-apple-silicon)
- [6. cue 帧的配额规则](#6-cue-帧的配额规则)
- [7. 720p 上限与无 cookie](#7-720p-上限与无-cookie)
- [8. 本地补丁清单](#8-本地补丁清单)
- [9. 已知无害告警](#9-已知无害告警)

---

## 1. 索引写入会删除旧数据

`index/store.py`:

```python
def video_id_for(source): return sha256(source.strip().encode())[:16]
```

**video_id 只取决于 source 字符串，与 `--start/--end` 无关。** 而
`index_watch_result → _insert_video` 在写入前：

```python
for table in ("segments","scenes","ocr_blocks","embeddings","answers"):
    conn.execute(f"DELETE FROM {table} WHERE video_id = ?", (video_id,))
conn.execute("DELETE FROM fts WHERE video_id = ?", (video_id,))
```

所以对同一 URL 的每一次带索引 watch 都会清空上一次的成果。分段观看如果每段都索引，
第 2 段就把第 1 段和全片转录一起删了——检索从此在残缺数据上工作，而且不会报错。

**因此**：阶段 1 全片 `--transcript-only` 是唯一索引写入点，阶段 2 每段都加 `--no-index`。

副作用：索引里只有转录段落，没有 scene / OCR 行。需要画面证据时靠升级阶梯的
`augment_video()` 按需补——那个函数的注释明确写 "nothing is deleted"，是 ADD 语义，安全。

## 2. 带索引的 watch 会静默调用云端视觉

`index/store.py: _maybe_describe_scenes()` 在每次索引末尾，用 **cheap 视觉档**
（默认 `anthropic` / `claude-haiku-4-5`）给最多 24 帧生成一句话描述。

它**完全不检查 `cost_policy`** —— `offline_only` 只在 `answer/engine.py:361` 生效。
无 key 时它 `except VisionError` 静默跳过，**有 key 就静默付费**，CLI 没有开关
（`index_watch_result(describe_scenes=)` 未暴露）。

**因此**：所有调用用 `env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u GEMINI_API_KEY
-u OPENROUTER_API_KEY` 包装。代价是 `scenes.description` 为 NULL，索引少一路证据——
可以接受，画面理解本来就由 Claude 直接读帧承担。

验证方法：stderr 出现 `scene descriptions skipped` 即正确。

## 3. 字幕轨按字母序回落

`acquire/ytdlp.py`:

- `_ensure_original_subs(out_dir, url, info)` 第一件事是
  `lang = (info.get("language") or "").split("-")[0].lower(); if not lang: return`
- `_pick_subtitle(out_dir, original_lang)` 只在 `original_lang` 有值时才优先原生轨，
  否则 `sorted(glob("media*.vtt"))` 取第一个

**实测**：`https://www.youtube.com/watch?v=LNH4I47ufLk`（中文教学视频）的 info.json
`language` 就是 `None`。这不是 B 站特有的疑虑，是默认情形。

所以自动兜底常常不触发，而字母序里 `media.en.vtt` 排在 `media.zh.vtt` 之前 →
会选中机翻英文轨去理解中文课程。

**因此**：`WATCHSKILL_SUBTITLE_LANGS='zh.*'`，不要带 `en.*`。语种由阶段 0 的探测结果
显式决定，不依赖引擎。

## 4. 中文检索的缺陷在查询侧

索引侧是好的：`index/textnorm.py: _segment()` 把 CJK **逐字**空格化，
`_fts_query` 把多字连排转成 FTS5 短语查 → 等价子串匹配，召回高、无未登录词问题。

问题在查询侧，两处，都是 `text.split()` 按空白切分：

1. `_fts_query`：中文整句无空格 → 整句成为**一个** token → 一条要求全句逐字相邻的
   短语查 → 几乎零命中。`hybrid_search` 权重是 0.45 FTS + 0.55 向量，于是 0.45 白扔。
2. `answer/confidence.py: lexical_anchor()`：同样按空白切分，且**丢弃长度 < 3 的词**
   （为英文虚词设计）。中文双字词全被丢掉。它在 `retrieval_confidence` 里权重
   **0.3**（与 margin 并列最高）→ anchor 恒为 0 → 置信度偏低 → 升级阶梯过度触发。

**因此**：中文查询写成「空格分隔的 3 字以上词组」。这一条同时修好两处，零依赖、无迁移。

备选补丁（未实施）：在 `_fts_query` 里对 CJK 连排做二元滑窗
（`配置代理服务器` → `配置 OR 置代 OR 代理 OR 理服 OR 服务 OR 务器`），并把
`lexical_anchor` 的长度下限对 CJK 降到 2。只改查询侧、不动 `text_norm` 列，
**不触发索引迁移**——这是它可行的关键。真正的分词器（ICU EP / wangfenjin-simple）
都要换 tokenizer 从而重建索引，且跨平台成本高，不做。

嵌入模型是 `paraphrase-multilingual-MiniLM-L12-v2`（384 维，本地 ONNX）。
实测中文↔英文余弦相似度 **0.5913**，无关中文句 **-0.0285** —— 跨语言检索确实成立，
所以中文提问可以命中英文转录。

## 5. whisper 档位与 Apple Silicon

`transcribe/local.py`:

```python
_RAM_LADDER = [(24.0,"medium"), (12.0,"small"), (6.0,"base"), (0.0,"tiny")]
_GPU_MODEL = "large-v3"   # 仅在检测到 NVIDIA GPU 时
```

`_available_ram_gib()` 优先用 psutil，而 **psutil 不在任何 extra 的依赖里** →
ImportError → 非 Windows 落到 `return 8.0` → 命中 `base`。

即：**任何 Apple Silicon 机器，无论物理内存多大，默认都选 `base`**。补装 psutil 后
本机可用内存 13.8 GiB → 选 `small`，仍不是 medium；`large-v3` 在原实现里 Apple
机器永远不可达。

`base` 的中文质量实测不可用（把「多参考图」写成「多餐口圖」、「真人短剧」写成
「真人短距」，且输出繁体）。

CTranslate2 4.8.1 实测：`get_cuda_device_count() = 0`，
`get_supported_compute_types('cpu') = {int8, float32, int8_float32}` —— **架构上没有
Metal / CoreML 后端**，Apple GPU 完全闲置。

实测对比（同一段 60s 中文音频）：

| 后端 / 模型 | wall | RTF | 质量 |
|---|---|---|---|
| CT2 CPU `base` | 4.2s | 0.07x | 繁体，错字密集 |
| CT2 CPU `medium` | 37.1s | 0.62x | 简体，准确 |
| mlx `base` 热 | 0.8s | 0.01x | 同 base 质量 |
| **mlx `large-v3-turbo` 热** | **2.8s** | **0.05x** | **简体准确，最优** |

**因此**：显式 `WATCHSKILL_WHISPER_MODEL=large-v3-turbo`，走本地 mlx 补丁。
13.7 分钟视频转录约 41 秒。

即便 large-v3-turbo 也有同音误识（`短距` / `短剧`）——声学模型解决不了同音词，
这就是「OCR 优先于转录」规则的由来。

## 6. cue 帧的配额规则

`perceive/engine.py`:

- `pinned_reasons = frozenset({"cue"})` —— cue 帧被钉住
- `detail_target = max(0, target - len(cues))` —— 先给 cue 留额，剩下的才给场景采样
- 但 `cues = _even_sample(cues, cap)` —— **cue 数超过 cap 会被抽稀**

所以 cue 定位有效的前提是 **cue 数 ≤ `--max-frames`**。超了就等于白定位，而且不报错。

## 7. 720p 上限与无 cookie

`acquire/ytdlp.py`:

```python
fmt = "ba/bestaudio" if audio_only else "bv*[height<=720]+ba/b[height<=720]/bv+ba/b"
```

外加源码注释里的隐私不变量："no cookies, no logins — yt-dlp only ever requests
public data"。`bradautomates/claude-video` 的对应代码完全相同（两者同源）。

**推论**：
- `--resolution 1024/1280` 只是决定帧的宽度，**不会比 720p 源更清晰**；
- 「让用户提供 cookie 换高清」这条路**不存在**，引擎不接受 cookie；
- 实测样本源是 2560×1440，被砍到 720p，与登录无关。

唯一出路是用户自备本地高清文件。或者打补丁放宽格式串到 `height<=1440`
（一行改动，**当前未采纳**）——采纳时须同步把 `--resolution` 提到 1600~1920，
token 成本约 2.4k/帧，只对含代码/界面的视频启用。

## 8. 本地补丁清单

分支 `local-patches`，基线 `bf177b0`。上游更新时 rebase 这三个 commit。

| 补丁 | 文件 | 内容 |
|---|---|---|
| mlx-whisper 后端 | 新增 `transcribe/mlx_backend.py`，改 `transcribe/local.py` | Apple Silicon 优先走 mlx（GPU），默认 `large-v3`，失败自动回退 CT2；`WATCHSKILL_WHISPER_BACKEND=ctranslate2` 可关闭 |
| RapidOCR 开 CoreML | `perceive/ocr.py` 新增 `_coreml_params()` | 注入 `EngineConfig.onnxruntime.use_coreml=True`。必要性：`ProviderConfig.is_coreml_available()` 第一行就是 `if not self.cfg_use_coreml: return False`，而 `config.yaml` 出厂 `false`，上游从不设置 → OCR 一直跑 CPU EP，尽管 onnxruntime 1.28 在 macOS arm64 确实暴露 `CoreMLExecutionProvider`。**实测收益仅约 9%**（324 vs 355 ms），因为模型是动态形状、多数子图回退 CPU，详见第 9 节。同时把编译缓存从 `/tmp/RapidOCR` 移到 `<data_dir>/models/ocr/coreml-cache`（macOS 会清理 /tmp） |
| 补装 psutil | `uv tool install --with psutil` | 修好第 5 节的内存探测。注意 `doctor` 的内存检查是另一条代码路径，仍显示 `warn`，属上游 cosmetic 问题，不影响选档 |

重装命令：

```bash
uv tool install --force --python 3.11 --with psutil --with mlx-whisper \
  --editable "$WATCH_SKILL_SRC"   # 你 clone watch-skill 的位置
```

## 9. 已知无害告警

**dylib 冲突**：`cv2` 与 `av` 各自打包 `libavdevice`，运行时 objc 报
`Class AVFFrameReceiver is implemented in both ...`，提示 "may cause spurious casting
failures and mysterious crashes"。所有实测运行未见实际故障。若后续出现莫名崩溃，
优先怀疑此处。

**CoreML OCR 的 `E5RT` 刷屏 —— 而且它不只是噪音**：开启 CoreML EP 后（本地补丁 2），
stdout 会出现大量 `E5RT encountered an STL exception ... has unbounded dimension which is
not supported` 的日志。**实测确认这不是无害噪音**：PP-OCR 的 det/rec 模型是动态输入形状，
CoreML 编译不了，大部分子图**回退到 CPU 执行**。

**实测收益只有约 9%**（同一 ROI 重复 6 次：CoreML 开启中位 324 ms vs 纯 CPU 355 ms）。
所以补丁 2 是有效的但收益边际，**不要按「GPU/ANE 加速」来预期**。想要真正的加速需要把
输入固定成静态形状（例如把 ROI 统一 pad 到固定尺寸再送入），那是未验证的改造方向。

读取输出前仍必须过滤：

```bash
... "$WATCH_SKILL_BIN" watch ... 2>&1 | grep -v "E5RT"
```

代价是本地补丁 2 换来的加速附带了这个副作用；不想要就把 `use_coreml` 关掉，OCR 退回 CPU。
