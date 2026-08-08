# video-distill 设计文档(v3,引擎换装 + 阻塞修正版)

日期:2026-07-31
状态:待用户批准
项目:`/Users/vdev/Claude/Projects/video`
修订说明:v3 基于对 `bradautomates/claude-video` 与 `oxbshw/watch-skill` **源码级逐行核对**,做出三项结构性修改:
1. **观看引擎由 claude-video 换为 watch-skill(仅作为 CLI 引擎使用,不装其插件)** —— 决定性理由是中文/多语言字幕与本地转录(见第 2 节);
2. **抽帧策略改为"转录驱动的两遍法"**(`--transcript-only` → `--timestamps`),取代 v2 的盲抽帧;
3. 修正 v2 的两处硬阻塞(B 站清晰度补救不成立、外部字幕无注入通道)与一处自伤规则(validate 全局时间戳校验)。

---

## 1. 目标

建立 `video-distill` skill,能够:

1. **完整理解**教学类视频(YouTube / Bilibili / 本地文件),含图表、操作演示、语音、字幕、画面文字;
2. **沉淀知识点**为结构化、带时间戳、可回查的 Obsidian 笔记,按分类组织;
3. **产出操作指导**(操作型视频):不看视频、只凭文档即可复现操作;
4. **扩展知识**,与视频原文严格区分来源;
5. (可选)将方法论型内容蒸馏成可调用的 Agent Skills。

**主要语料假设:中文教学视频为主,英文为次,其他语种偶发。** 这一假设直接决定第 2 节的引擎选型。

## 2. 引擎选型:claude-video vs watch-skill(v3 核心变更)

两者同源(相同的 720p 上限格式串、相同的"无 cookie"隐私不变量、相同的"Claude 自己 Read 帧"模型),差异集中在**转录与画面文字**这一层——恰好是中文教学场景的关键路径。

### 2.1 源码级对比

| 维度 | claude-video (bradautomates) | watch-skill (oxbshw) | 对中文教学的影响 |
|------|------|------|------|
| 字幕语言 | `--sub-langs "en.*"` **硬编码**(`download.py:78,135`),无配置项 | 默认 `en.*`,但**可配**(`WATCHSKILL_SUBTITLE_LANGS`),且有 `_ensure_original_subs()`:读 info.json 的 `language` 字段,**自动补拉原生语言字幕轨** | **决定性**。中文视频在 claude-video 下拿不到原生字幕;watch-skill 开箱即得 |
| 字幕轨优先级 | 只挑含 `.en.` 的,否则取目录里第一个 | `_pick_subtitle(original_lang)` **原生语言轨 > 非 -orig 变体 > 其他**,注释明确"英文轨在阿拉伯语视频上是机翻,不是口述内容" | **决定性**。避免用 YouTube 机翻英文轨去理解中文课程 |
| 语音转录 | **仅云端** Whisper(Groq/OpenAI),需 API key;单文件 **25MB 上限**(约 50 分钟),超限需 ffmpeg 切块 | **本地 faster-whisper 默认开启、无需 key、无体积上限**;云端 STT 为 opt-in(`cloud_stt_enabled=False`) | 长视频无需切块;无 key 成本;隐私 |
| 画面文字 | 无 OCR,完全依赖 Claude 读帧 | **OCR pass 默认开(RapidOCR + onnxruntime)**,OCR 文本随帧报告一起输出;`ocr_backend=auto` 按文字系统路由 | 代码/终端/界面文字有**机器可读的第二来源**,可与 Claude 的视觉读数交叉校验,直接压低 v2 里 `[画面文字不可读]` 的发生率 |
| 本地文件 | `resolve_local()` 返回 `subtitle_path=None` → **本地文件必走云端 Whisper**,无 key 则纯视觉 | 本地文件同样走本地 whisper + OCR | B 站高清只能靠本地文件(见 2.3),此项因此权重很高 |
| 下载缓存 | 无;分段观看需靠共用 `--out-dir` 规避重复下载 | 内置下载缓存(LRU,默认 20GB 上限)+ `--no-cache` | 分段观看天然不重复下载 |
| 抽帧 | 场景感知 + 去重,`--detail` 四档(transcript/efficient/balanced/token-burner) | 场景检测 + **感知哈希去重**(phash 距离 6);无 `--detail` 档位,用 `--max-frames/--resolution/--transcript-only` 直控 | 平手。watch-skill 的 phash 去重对"静态幻灯片讲解"更省帧 |
| 帧交付方式 | 打印帧路径,Claude 自己 `Read` | **同样**打印帧路径要求 Claude 并行 `Read`;自带 vision provider 仅用于可选的 `ask`/verify 通道 | 平手。**不存在"被小模型代看"的降质风险**,这点是选型前的主要疑虑,已排除 |
| flag 覆盖 | `--start/--end/--max-frames/--resolution/--fps/--timestamps/--detail/--out-dir/--no-whisper/--whisper/--no-dedup` | claude-video 的超集减 `--fps/--detail`,加 `--no-ocr/--cloud-stt/--whisper-model/--diarize/--duration/--no-cache/--no-index/--transcript-only` | watch-skill 略优 |
| 平台/清晰度 | `bv*[height<=720]`,**无 cookie 支持** | `bv*[height<=720]`,**无 cookie 支持**(源码注释为"隐私不变量") | **完全相同**,不构成选型依据(见 2.3) |
| 安装重量 | 极轻:两条 plugin 命令,brew 装 ffmpeg/yt-dlp | 重:Python 3.11+ / uv,extras 分组安装,首次跑要下 whisper 与 OCR 模型(数百 MB~GB) | claude-video 明显占优 |
| 成熟度 | 较早发布,使用量大 | **v1.0.0 于 2026-07-12 发布,约 3 周** | claude-video 占优,是本次选型的主要风险项 |
| 附带 skill 数量 | 1 个(`watch`) | 插件形式会装入 **9~10 个 skill**(watching-videos、the-loop、video-memory…) | 会与 video-distill 抢触发,须规避(见 2.2) |

### 2.2 结论:采用 watch-skill,但**只当引擎、不装插件**

**选它的理由**只有一条主干:本方案的语料以中文为主,而"拿到原生中文字幕"是整条流水线的地基。claude-video 在这一点上**不是配置不方便,是没有配置项**——只能靠"把自取的 `video.zh.vtt` 预置进 `<out-dir>/download/`、诱使 `_pick_subtitle()` 捡起来"这种依赖上游内部实现的 hack(v2 隐含、且未写明)。watch-skill 把这件事做成了带注释和测试的一等功能。附带拿到的本地转录(无 key、无 25MB 限制)和 CJK OCR,都正好落在中文教学视频的痛点上。

**安装方式(关键):不执行 `/plugin install watch-skill@watch-skill`。** 改为只装引擎:

```bash
# 推荐:用本机已有的 uv 托管 CPython 3.11.15 (macos-aarch64) 装,不碰系统 Python 3.14
uv tool install --python 3.11 "watch-skill[perceive,ocr,whisper,index]"
# 备选:官方脚本(会用系统 Python,受下述 3.14 风险影响)
#   curl -fsSL https://raw.githubusercontent.com/oxbshw/watch-skill/main/scripts/install.sh | sh
"$WATCH_SKILL_BIN" doctor      # 自动补 ffmpeg / yt-dlp / deno
```

**Python 版本选择(v3.3 新增)· 用 3.11,不用系统的 3.14**

本机情况:系统 `python3` 为 **3.14.6**;uv 已托管 **`cpython-3.11.15-macos-aarch64-none`**(`~/.local/share/uv/python/cpython-3.11-macos-aarch64-none/bin/python3.11`)。`requires-python = ">=3.11"`,两者都满足下限,但应选 3.11:

- **这套栈全是二进制轮子**,新版 Python 支持常滞后。沙箱交叉查询(macOS arm64)显示:`ctranslate2 4.8.1` 已有 cp314 轮子(faster-whisper 本身没问题),但 **`onnxruntime` 是硬门槛且不可绕过**——OCR(rapidocr)、嵌入(fastembed)、**以及 faster-whisper 自己的 VAD**(`Requires-Dist: onnxruntime<2,>=1.14`)三处都依赖它;
- 本次**未能确认** onnxruntime 有 cp314 macOS arm64 轮子(沙箱索引偏旧,只到 1.23.2,而 watch-skill 要求 ≥1.27);间接证据偏正面(`fastembed 0.8.0` 声明 `onnxruntime>=1.24.2 ; python_version >= "3.14"`,`onnxruntime-directml 1.24.4` 已带 cp314),但**没必要赌**;
- **3.11 是这套二进制栈轮子最齐全的版本**(连老版 `onnxruntime 1.19.2` 都有 cp311 arm64 轮子),且本机已就位、无需额外下载,同时避免污染系统 Python。

故安装命令固定为 `uv tool install --python 3.11 ...`。**不要**用 `curl install.sh | sh`(它会挑系统 Python,即 3.14)。若日后想升到 3.14,先验证:

```bash
uv pip download --only-binary=:all: --no-deps --python 3.14 -d /tmp/ort-probe "onnxruntime>=1.27"
```

理由:
- 装插件会引入 9~10 个 skill,其中 `watching-videos` 的 description 覆盖"用户丢来一个视频链接"这一整类意图,**必然与 video-distill 抢触发**;只装引擎则触发面由我们独占,video-distill 通过 Bash 调 `watch-skill` CLI;
- 跳过 `mcp / api / loop` 三个 extras:MCP 服务与 REST 对本方案无用,THE LOOP(浏览器自检)完全无关;
- **保留 `index` extra 并开启索引**(v3.1 修正,理由见 2.4)——原判断"index 只服务跨视频检索、属非目标"是错的:它同时是**段内时刻定位**与**免模型证据回补**的基础设施,且中文检索离开向量半边基本不可用。

**保留 claude-video 作为记录在案的备选**,切换触发条件:
- 用户不愿装 Python/uv 技术栈,或机器上模型下载不可行 → 退回 claude-video,并接受"中文视频走字幕注入 hack 或纯 Whisper 云端转录";
- watch-skill 因过新出现阻塞性 bug 且无解 → 同上。
README 需写明这条退路及其代价。

### 2.3 两个引擎共有的硬限制(不因选型改变)

1. **视频清晰度上限 720p**:两者格式串都是 `bv*[height<=720]+ba/b[height<=720]/bv+ba/b`。所以 `--resolution 1024` 只是把 1280 宽的帧降到 1024,**不会比 720p 源更清晰**。

   **补救 D(v3.3 新增,建议采用)· 放宽 720p 上限**:实测样本(附录 D)的 YouTube 源是 **1440p**,却被格式串砍到 720p——**这与 cookie / 登录无关,纯粹是引擎写死**。对"看清代码与界面"这一核心诉求,把 `download_url` 的格式串改成 `bv*[height<=1440]+ba/b[height<=1440]/bv+ba/b`(或做成配置项)是**一行改动、收益最大**的补丁,优先级应高于 2.5 的补救 B(CJK 分词)。代价:下载体积与抽帧耗时上升,需同步把 `--resolution` 提到 1600~1920 才吃得到分辨率红利,token 成本随之上升(约 2.4k token/帧 @1920 宽),因此**只对"含代码/界面演示"的视频启用**,由阶段 0 判定。
   - 未打补丁时:仍按 720p + `--resolution 1280` 走,并把"源为 1440p 但被降到 720p"记入 `degradations`。
2. **不支持 cookie / 不登录**:两者源码均把"无 cookie、无登录"写成隐私不变量。因此 **v2 里"请用户提供 cookie"的补救不成立**。B 站未登录清晰度受限且含代码/界面的视频,唯一出路是**用户自备本地高清文件**(而 watch-skill 对本地文件支持更完整,见 2.1)。

### 2.4 嵌入模型与索引层的定位(v3.1 新增)

**先划清边界:嵌入模型对"转写准确度"零贡献。** 它作用在 transcript 与 OCR **之后**,索引对象是三类**已有文本**(转录段落 `segment`、场景描述 `scene`、OCR 文本 `ocr`),全部带时间戳存入 SQLite。它不参与语音识别,也不参与画面理解——不会让 faster-whisper 多认一个字,也不会让 Claude 看帧更清楚。它解决的是**"在已有证据里定位时刻"**。

模型:`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`(本地 ONNX via fastembed,384 维,+130MB,无 torch)。检索为 FTS5 关键词 + 向量混合召回(`index/retrieval.py: hybrid_search`)。

**对本方案的四处实际价值:**

1. **cue 定位从关键词碰运气升级为语义召回**(改进 5.2)。原设计靠正则匹配"你看这里 / 打开设置 / 报错"等指示语,脆弱且漏召。改为对索引做语义检索(如"哪些时刻在演示具体操作步骤 / 出现代码 / 出现报错"),返回带时间戳的 hits 直接喂 `--timestamps`。
2. **免模型的证据回补阶梯**(改进 5.2 转写规则与 6.3 盲测)。`answer/ladder.py` 的升级顺序是:文本优先 → `dense_resample`(候选时刻附近高分辨率密集重抽 + OCR)→ `crops.py: crop_and_reocr`(按 OCR 自身 box 裁剪、2× 放大、重新 OCR)→ **最后**才考虑视觉模型。前两步源码注释明确 "No model calls",代价只是本地算力,且**恢复的证据会 merge 回索引**("the next ask starts smarter")。这正是 `[画面文字不可读 @mm:ss]` 的自动补救路径。
3. **中文场景下它决定检索是否可用**。SQLite FTS5 无中文分词器;`index/textnorm.py` 把 CJK **逐字切分**写入 `text_norm` 列,使两字词能作短语查(见 `_fts_query` docstring)。即:中文的关键词半边是硬做出来的,**向量半边才是主力**。英文视频丢掉向量只是退化,中文视频丢掉向量近乎没有检索。
4. **跨语言检索**。`docs/DECISIONS.md:166` 的 A/B:旧英文 MiniLM 在 ar→ar 检索上直接失败(相关段落排在干扰项之下),换多语言模型后 ar→ar 0.55、**跨语言 en→ar 0.58**(干扰项约 0)。对本方案:**笔记为中文而视频为英文时,用中文提问可命中英文转录**——阶段 3 写笔记与事后追问都受益。

附带:`answer/cache.py` 提供语义缓存;索引持久化后,断点续跑与事后补问不必重下载重转录。

**代价与配置:**

- `index` extra = fastembed + numpy;模型 +130MB;加载有冷启动延迟(`DECISIONS.md:208`);每次 watch 写一次 SQLite;
- **不更换嵌入模型**。`embedding_model` 可换 `bge-m3` / `multilingual-e5-large`,但仅对**新建**索引生效(索引 meta 会 pin 模型,防止查询向量与存储向量不同源),且 1024+ 维、>2GB,上游为 8GB 内存机器拒掉。默认模型已是多语言,够用;
- **必须设 `WATCHSKILL_COST_POLICY=offline_only`**:`ask` 的升级阶梯末端可能调云端视觉,该策略锁死在无 key / 本地路径,云端永不见帧。

### 2.45 索引写入的两个陷阱(v3.3 新增,**实施前必读**)

源码核对发现两处会直接破坏 2.4 设计的行为,都不在文档或 README 里:

**陷阱 1 · 重新索引同一 source 会清空该视频的旧索引**

`index/store.py: video_id_for(source) = sha256(source)[:16]` —— **video_id 只取决于 source 字符串**,与 `--start/--end` 无关。而 `index_watch_result → _insert_video` 在写入前执行:

```python
for table in ("segments", "scenes", "ocr_blocks", "embeddings", "answers"):
    conn.execute(f"DELETE FROM {table} WHERE video_id = ?", (video_id,))
conn.execute("DELETE FROM fts WHERE video_id = ?", (video_id,))
```

后果:阶段 2 分段观看时,**第 2 段会删掉第 1 段、以及阶段 1 全片转录的全部索引**。cue 检索与 `ask` 从第 2 段起就在残缺索引上工作(与 v2 "在残影上工作"是同一类错误,只是换了层)。

**修正(已落入 5.1 / 5.2)**:
- **阶段 1 全片 `--transcript-only` 必须带索引**(不加 `--no-index`)——这是唯一的索引写入点,覆盖全片转录;
- **阶段 2 的每段 watch 必须加 `--no-index`**,只取帧与 OCR 文本供 subagent 直接 `Read`,不入库;
- 于是索引内容 = 全片转录段落(无 scene / OCR 行)。`ask` 需要画面证据时,由升级阶梯的 `augment_video()` **按需 ADD**(该函数注释明确 "nothing is deleted"),自洽且不破坏索引。

**陷阱 2 · 带索引的 watch 会静默调用云端视觉,且 `cost_policy` 管不住它**

`index/store.py: _maybe_describe_scenes()` 在每次带索引的 watch 末尾,用 **cheap 视觉档**(默认 `anthropic` / `claude-haiku-4-5`)为最多 **24 帧**生成一句话描述。它**完全不检查 `cost_policy`**——`offline_only` 只在 `answer/engine.py:361` 生效。无 key 时它 `except VisionError` 静默跳过;但**环境里存在 `ANTHROPIC_API_KEY` 就会静默付费**,且 CLI 没有开关可关(`index_watch_result(describe_scenes=)` 未暴露到 CLI)。

**修正**:SKILL.md 规定所有 watch-skill 调用一律用 `env -u` 剥掉视觉相关 key:

```bash
env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u GEMINI_API_KEY -u OPENROUTER_API_KEY \
    watch-skill watch ...
```

代价:`scenes.description` 为 NULL,索引少一路 `scene` 证据。可接受——我们的画面理解由 Claude 直接读帧承担,不依赖它。

**附带说明**:`_distill_notes_safely → library/notes.py: distill_notes()` 会在每次索引后自动生成 watch-skill 自己的 library notes(存 `notes_fts` / notes embedding 表)。**这不是我们的产物**,与 Obsidian 笔记无关,失败也静默跳过;只需知道它会占一点时间,别误认。

### 2.5 中文检索的查询侧缺陷与补救(v3.2 新增)

2.4 说"中文检索靠向量半边"仍不够精确。**问题不在索引侧,在查询侧**,且有两处,第二处影响成本:

**现状**:索引侧 `index/textnorm.py: _segment()` 把 CJK **逐字**空格化(`" 机 器 学 习 "`),配合 `_fts_query` 把多字连排转为 FTS5 短语查 → 等价于**子串匹配**,召回高且无未登录词问题。索引侧没有问题。

**缺陷 1 · FTS 半边退化**:`_fts_query` 用 `text.split()` 按**空白**切分。中文查询"如何配置代理服务器超时"无空格 → 整句成为**一个** token → 一条要求全句逐字相邻的短语查 → 几乎必然零命中。`hybrid_search` 的固定权重是 0.45 FTS + 0.55 向量,于是 **0.45 的权重被白扔**,混合检索退化成纯向量。

**缺陷 2 · 置信度被系统性压低 → 过度升级(更值得注意)**:`answer/confidence.py: lexical_anchor()` 同样用 `question.split()`,检查"问题实词是否字面出现在证据里";它在 `retrieval_confidence` 中权重 **0.3(与 margin 并列最高)**。中文整句不可能字面出现在证据文本里 → anchor 恒为 0 → 置信度偏低 → `answer/ladder.py` **过度升级**(多跑 dense_resample、多做裁剪重 OCR,更易触及视觉模型)。即中文场景不只是"检索差一点",还会多花本地算力甚至云端调用。

**补救 A(采用,零代码)· 查询侧词组约定**:SKILL.md 规定——所有传给 `watch-skill search / ask` 的中文查询,写成**空格分隔的、3 字以上的中文词组**。

```bash
# ✗ watch-skill ask <id> "如何配置代理服务器超时"
# ✓ watch-skill ask <id> "代理服务器 超时配置 网络设置"
```

- 空格分隔后每个词组各成一条短语子句、OR 组合 → FTS 半边恢复正常 BM25 行为;
- **为什么是"3 字以上词组"而非"分词"**:`lexical_anchor` 会丢弃 `len < 3` 的词(为英文短虚词设计),而中文词多为双字——"配置"会被丢掉。故双字词应并成四字词组(`超时配置`、`环境变量`),或接受它只对 FTS 生效、对 anchor 无效;
- 这一条约定同时修好两处缺陷,零依赖、无迁移。**5.2 的 cue 检索查询与 6.3 的缺口回补提问都必须遵守此约定**。

**补救 B(可选,~20 行,视 A 的实测效果再定)· 给上游打查询侧补丁**:在 `_fts_query` 中对 CJK 连排段做**二元滑窗**而非整段短语(`配置代理服务器` → `配置 OR 置代 OR 代理 OR 理服 OR 服务 OR 务器`,CJK 检索经典做法,无字典依赖);同时把 `lexical_anchor` 的长度下限对 CJK 降到 2。**只改查询侧、不动 `text_norm` 列,因此不触发索引迁移**——这是它可行的关键。若追求更高精度可换 jieba,代价是新增依赖。可向上游提 PR。

**补救 C(否决)· 真正的 SQLite 中文分词器**:ICU tokenizer 需 SQLite 编译带 `SQLITE_ENABLE_ICU`(CPython 自带 sqlite3 一般不带,须换 `pysqlite3-binary` / apsw);`wangfenjin/simple`(jieba + 拼音)是可加载扩展,需 `enable_load_extension`(macOS 系统 Python 常禁用)且要按平台分发二进制。两者维护成本远超收益,**且都会改变 tokenizer 从而必须重建索引**(A/B 不需要)。

**冒烟测试新增第 6 项**:用中文查询验证 FTS 半边确实贡献命中——同一语义分别用"整句无空格"与"空格分隔 3 字词组"查询,对比命中数与排序;确认后者显著更好,再把约定写死进 SKILL.md。

### 2.6 本机部署决定与三个本地补丁(v3.4,已实施)

**环境**:Apple Silicon **M2 Pro**;uv 托管 CPython **3.11.15**;系统 `python3` 为 Homebrew 3.14.6(不使用);watch-skill 以 **editable** 方式装自 `vendor/watch-skill`(见下)。

#### 2.6.1 转录质量实测:默认档位不可用于中文知识沉淀

同一段 60s 中文音频(附录 D.1 样本 01:00–02:00),CPU int8:

| 模型 | 加载 | 转录 | RTF | 输出 |
|------|------|------|-----|------|
| `base`(**auto 实际选中**) | 0.6s | **4.2s** | 0.07x | **繁体**,错字密集:`多餐口圖`/`真人短距`/`真人AI短訊`/`壓收到1-5塊錢` |
| `medium` | (下载 645s) | **37.1s** | 0.62x | **简体**,准确:`多参考图`/`真人短剧`/`压缩到1-5块钱` |

两个结论:

1. **`base` 的中文质量不可用**——错字会直接污染笔记与后续检索;
2. **简繁问题在 medium 上自行消失**(base 输出繁体,medium 输出简体)→ **不需要 opencc 后处理**,原计划中的简繁转换取消。

#### 2.6.2 为什么 auto 会选中 base(两层原因)

- `transcribe/local.py: _RAM_LADDER = [(24.0,"medium"),(12.0,"small"),(6.0,"base"),(0.0,"tiny")]`,`_GPU_MODEL="large-v3"` **仅在检测到 NVIDIA GPU 时启用**;
- 内存探测 `_available_ram_gib()` 优先用 **psutil,而 psutil 不在任何 extra 的依赖里** → `ImportError` → 非 Windows 平台落到 `return 8.0` 的保守默认 → 命中 `base`。

即:**在任何 Apple Silicon 机器上,无论物理内存多大,默认都会选到 `base`**。补装 psutil 后实测可用内存 13.8 GiB → ladder 选 `small`,**仍不是 medium**;`large-v3` 在原实现里 Apple 机器**永远不可达**。

#### 2.6.3 CTranslate2 在 Apple Silicon 上没有 GPU 路径

实测 `ctranslate2 4.8.1`:`get_cuda_device_count() = 0`,`get_supported_compute_types('cpu') = {int8, float32, int8_float32}`。**架构上没有 Metal / CoreML 后端**,M2 Pro 的 GPU 完全闲置。上游 `DECISIONS.md:162` 拒绝 whisper.cpp 的理由是"在该机器上对 CT2 无实测 CPU 优势"——但那台参考机是 **8GB CPU-only Windows**,结论不迁移到 Apple Silicon。

#### 2.6.4 三个本地补丁(vendor 化,可 rebase)

仓库 clone 到 **`vendor/watch-skill`**,建 `local-patches` 分支(基线 `bf177b0`,2026-07-12),以 `uv tool install --editable` 装入。这样上游更新可 rebase,且改动进本项目版本管理。

| # | 补丁 | 内容 |
|---|------|------|
| 1 | **mlx-whisper 后端** | 新增 `transcribe/mlx_backend.py`;`transcribe_local()` 在 Apple Silicon 上优先走 mlx(GPU),默认档位 `large-v3`,失败自动回退 CTranslate2;`WATCHSKILL_WHISPER_BACKEND=ctranslate2` 可关闭 |
| 2 | **RapidOCR 开 CoreML** | `perceive/ocr.py` 新增 `_coreml_params()`,注入 `EngineConfig.onnxruntime.use_coreml=True`。必要性:`ProviderConfig.is_coreml_available()` **第一行就是** `if not self.cfg_use_coreml: return False`,而 `config.yaml` 出厂 `use_coreml: false`,上游从不设置 → OCR 一直跑 CPU EP,尽管 onnxruntime 1.28 在 macOS arm64 **确实暴露** `CoreMLExecutionProvider`。同时把编译缓存从 RapidOCR 默认的 `/tmp/RapidOCR` 移到 `<data_dir>/models/ocr/coreml-cache`(macOS 会清理 /tmp,否则每次重付编译成本) |
| 3 | **补装 psutil** | `uv tool install --with psutil`,修好 2.6.2 的探测。**注意**:`doctor` 的内存检查是另一条代码路径,仍显示 `warn: could not probe system memory`——不影响实际选档,属上游 cosmetic 问题 |

**未采纳的补丁**:放宽 720p→1440p(2.3 补救 D)。当前按 720p + `--resolution 1280` 走,并把"源为 1440p 但被降到 720p"记入 `degradations`。

#### 2.6.4.1 mlx 补丁实测(同一 60s 音频)

| 后端 / 模型 | wall | RTF | 说明 |
|---|---|---|---|
| CT2 CPU `base` | 4.2s(+0.6s 加载) | 0.07x | 基线 |
| **mlx `base` 冷启** | **3.5s** | 0.06x | `source=whisper-mlx (base)`,补丁通路确认生效 |
| **mlx `base` 热** | **0.8s** | **0.01x** | 约 60× 实时,比 CT2 同档快 ~5× |
| CT2 CPU `medium` | 37.1s | 0.62x | 质量达标但慢 |
| **mlx `large-v3-turbo` 冷启** | **4.9s** | 0.08x | 权重 1.5GB,已就位 |
| **mlx `large-v3-turbo` 热** | **2.8s** | **0.05x** | **比 CT2 medium 快 13×,且质量更好** |

**最终选型:`large-v3-turbo` + mlx。** 13.7 分钟视频的转录用时从 CPU medium 的 **8.5 分钟**降到约 **41 秒**。这使"每个视频都用大模型"从不现实变成默认可行,也让 5.1 的"转录优先"第一遍成本可以忽略不计。

`large-v3-turbo` 中文输出实测(同一段):

```
[  0.0] 像一个我最近做的东西
[  1.2] 我把LTX2.3的多参考图真人短距的这整个制作流程
[  6.0] 封装成了一个自动化的桌面的智能体
[ 14.7] 成本可以直接压缩到1到5块钱
```

简体、专有名词准确。**仍有一处同音误识:`短距` 应为 `短剧`**——而 OCR 在同批帧上正确读出了 `真人 AI 短剧`。这是 2.6.5 "OCR 反向纠正转录"规则最直接的实证:声学模型再大也解决不了同音词,画面文字才是这类专名的可靠来源。

**权重下载备注**:首次尝试时 HF 未认证限速导致 `large-v3`(3GB)卡在 1.03GB、`turbo` 卡在 0 字节;稍后重试即以约 25MB/s 完成(1.5GB / 约 60 秒)。属瞬时限速而非稳定障碍。若再遇停滞:设 `HF_TOKEN`,或用 `huggingface_hub.snapshot_download(..., max_workers=4)` 续传。降级路径(`WATCHSKILL_WHISPER_MODEL=medium` + `WATCHSKILL_WHISPER_BACKEND=ctranslate2`)保留在文档中备用。

#### 2.6.5 OCR 反向纠正转录(v3.4 新增的转写规则)

实测同一批帧,OCR 中文识别**优于 base whisper**:OCR 正确读出 `多参考图`、`自动化智能体`、`成本低至1到5元`、`单集生成成本`,而 whisper(base)把同一词写成 `多餐口圖`。教学视频的标题字幕往往就是讲稿摘要,因此:

> **新增规则**:段落笔记里的专有名词、命令、参数值,若 OCR 与转录不一致,**以 OCR 为准**并标注;仅当 OCR 缺失该词时才采信转录。

OCR 自身也有错(`折解与提示词`应为`拆解`、`输入刷本`应为`剧本`、`空国合优室`为噪声),所以是**互补**而非单方可靠——这恰好是 5.2 "交叉校验"设计的实证依据。

#### 2.6.6 已知无害告警

`cv2` 与 `av` 各自打包 `libavdevice`,运行时 objc 报 `Class AVFFrameReceiver is implemented in both ...`,提示"may cause spurious casting failures and mysterious crashes"。本次全部运行未见实际故障,记录备查;若后续出现莫名崩溃,优先怀疑此处。

## 3. 依赖组件(v3 重写)

| 组件 | 角色 | 安装/配置 |
|------|------|------|
| watch-skill 引擎(CLI) | 观看引擎:下载、场景抽帧、OCR、转录、索引检索 | `curl … install.sh \| sh`(或 `uv tool install "watch-skill[perceive,ocr,whisper,index]"`);**不装其 plugin** |
| 多语言嵌入模型 | 时刻定位、证据回补、跨语言检索(见 2.4) | 随 `index` extra,首次运行自动下载(+130MB);**不更换默认模型** |
| ffmpeg / yt-dlp | 底层依赖 | `watch-skill doctor` 自动安装 |
| faster-whisper 模型 | 本地转录 | 首次运行自动下载(`whisper_model=auto` 按内存选档);**无需任何 API key** |
| RapidOCR 模型 | 画面文字 | 首次运行自动下载 |
| cangjie-skill(可选) | 方法论蒸馏 | `git clone https://github.com/kangarooking/cangjie-skill ~/.claude/skills/cangjie-skill`(仓库根即 skill 目录,含 SKILL.md) |
| obsidian 技能组 | 笔记写入、OFM 语法 | 已安装 |

**环境变量**(写入 `~/.config/watch-skill/` 或 shell profile,前缀 `WATCHSKILL_`):

```
WATCHSKILL_SUBTITLE_LANGS=zh.*                           # 只拉中文,理由见下"字幕轨字母序陷阱";英文视频临时覆盖为 en.*
WATCHSKILL_FRAME_WIDTH=512                               # 默认;需读屏幕文字时用 --resolution 覆盖
WATCHSKILL_CLOUD_STT_ENABLED=false                       # 显式保持本地转录
WATCHSKILL_COST_POLICY=offline_only                      # ask 阶梯锁死在本地/无 key 路径(注意:管不住 2.45 陷阱 2)
WATCHSKILL_WHISPER_MODEL=large-v3-turbo                  # 必须显式指定:auto 在 Apple Silicon 上必落 base(见 2.6.2)
# WATCHSKILL_WHISPER_BACKEND=ctranslate2                 # 仅在需要绕开 mlx 补丁时开启
```

**字幕轨字母序陷阱(v3.3 新增,已实测确认)**:`_pick_subtitle(out_dir, original_lang)` 只在 `original_lang` 有值时才优先原生轨;而 `original_lang` 来自 info.json 的 `language` 字段,`_ensure_original_subs()` 在该字段缺失时**直接 return**。

**实测结果(附录 D):中文 YouTube 样本的 `language` 就是 `None`。** 所以这不是"B 站可能有的疑虑",而是**默认情形**:引擎的原生语言自动兜底在这类视频上**根本不会触发**,`_pick_subtitle` 回落到 `sorted(glob("media*.vtt"))` 的**字母序**——`media.en.vtt` 排在 `media.zh.vtt` 之前,**会选中英文机翻轨**。

**因此**:`WATCHSKILL_SUBTITLE_LANGS` 默认只配 `zh.*`(不带 `en.*`),把语种选择交给我们在阶段 0 依据探测结果显式设定,**不依赖引擎兜底**。这削弱了 2.1 表中"字幕轨优先级"一栏的选型优势(该机制常不触发),但**不影响选型结论**——决定性优势转为"可配置的 `SUBTITLE_LANGS` + 本地免 key 转录",而 claude-video 连前者都没有。

**yt-dlp 的 JS runtime 依赖(v3.3 新增,实测发现)**:实测中 yt-dlp 报 `No supported JavaScript runtime could be found ... YouTube extraction without a JS runtime has been deprecated, and some formats may be missing`。watch-skill 的 `_run_yt_dlp` 会先调 `prepend_bin_dir_to_path()`,注释写明 "yt-dlp must find the managed deno for YouTube n-sig"——即**它自带 deno 管理,正是为此**。推论:preflight 必须确认 `watch-skill doctor` 已装好 deno;若用户绕过引擎、自己直接调 yt-dlp,YouTube 提取会降级(格式缺失、可能连字幕列表都不准)。

**命令包装(v3.3 新增)**:因 2.45 陷阱 2,SKILL.md 里所有调用统一走一个包装形式:

```bash
env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u GEMINI_API_KEY -u OPENROUTER_API_KEY \
    "$WATCH_SKILL_BIN" <subcommand> ...
```

`$WATCH_SKILL_BIN` 为 preflight 解析出的**绝对路径**(`uv tool install` 默认装到 `~/.local/bin`,subagent 的 bash 不保证继承该 PATH),解析结果固化进 SKILL.md 或 `~/.claude/CLAUDE.md`。

**依赖冒烟测试(实施前置动作,不可省)**:用一个 1 分钟**中文**短视频实测并把真实命令写进 SKILL.md:

1. `watch-skill watch <url> --transcript-only` → 确认拿到的是**中文原生字幕**而非机翻英文(检查 `media.zh*.vtt` 存在、内容为中文);**同时 dump info.json 确认 B 站是否提供 `language` 字段**(决定能否依赖引擎自动兜底,见第 3 节字幕轨陷阱);
2. 无字幕的本地 mp4 → 确认本地 faster-whisper 出中文转录、无需 key;
3. `--timestamps 0:05,0:30 --resolution 1280 --no-index` → 确认定点抽帧、cue 帧确实被保留、OCR 文本随帧输出;
4. `--start/--end`、`--max-frames`、`--out-dir` 逐项确认;**并验证第二段跑同一 URL 时复用下载缓存、不重复下载**;
5. **索引不被清空验证(对应 2.45 陷阱 1)**:全片 `--transcript-only`(带索引)→ `watch-skill search <中文词组>` 记录命中数 → 再跑一段 `--start/--end --no-index` → 重新 search,**命中数应不变**;若变则说明 `--no-index` 未生效,方案需重新设计;
6. **中文查询 A/B(对应 2.5)**:同一语义分别用"整句无空格"与"空格分隔 3 字词组"查询,对比命中数与排序;确认后者显著更好,再把约定写死进 SKILL.md;
7. **静默付费验证(对应 2.45 陷阱 2)**:在**有** `ANTHROPIC_API_KEY` 的环境跑一次带索引的完整 watch,观察 stderr 是否出现 scene description 相关输出;再用 `env -u` 包装重跑,确认出现 `scene descriptions skipped`;
8. 记录首次运行的模型下载体积与耗时、以及 `~/.local/share/watch-skill`(或 `data_dir`)的磁盘增量,写进 README 的"首次使用预期"。

## 4. 目录结构

### 4.1 skill 项目(本仓库)

```
/Users/vdev/Claude/Projects/video/
├── .claude/skills/video-distill/
│   ├── SKILL.md                  # 流程规范(rigid checklist)
│   ├── templates/
│   │   ├── NOTES.md
│   │   ├── PLAYBOOK.md
│   │   └── EXTEND.md
│   └── scripts/
│       └── validate.py           # 产出校验(分层规则,见第 6 节)
├── docs/superpowers/specs/
└── README.md
```

**安装:软链到 `~/.claude/skills/video-distill`**(本 skill 与代码项目无关,需全局可用);本仓库作为开发与版本化载体。

### 4.2 笔记存储(Obsidian vault)

默认 vault `/Users/vdev/notes`(**待用户确认**;本机另有 `/Users/vdev/work`、`/Users/vdev/work/oneclick/vault`)。路径首次确认后写入 SKILL.md 或 `~/.claude/CLAUDE.md`,之后不再询问。

```
<vault>/视频笔记/
├── <分类>/                       # 复用已有分类;新建须用户确认
│   └── <slug>/                   # yt-<id> / bili-<BV号> / local-<文件名hash>
│       ├── <清洗后标题>.md        # 主笔记(完整层),入口
│       ├── PLAYBOOK.md           # 操作层(条件产出,见 5.3)
│       ├── EXTEND.md             # 扩展层(默认精简模式)
│       ├── transcript.md         # 原始转录存档(蒸馏前提,见 5.5)
│       └── assets/               # 证据帧,命名 mm-ss-描述.jpg
└── 视频索引.base                  # Obsidian Bases 视图(需 1.9+,否则降级见下)
```

**命名与链接规则**:

- 文件名清洗:替换 `/ \ : # ^ [ ] |` 等非法及破坏 wikilink 的字符,上限 80 字符,不含 emoji;
- 互链一律用**完整路径 wikilink**(`[[视频笔记/编程开发/bili-BV1xx/PLAYBOOK|操作手册]]`)——各视频目录下 PLAYBOOK/EXTEND 同名,短链接会歧义;
- 时间戳锚点为可点击链接:YouTube `&t=<秒>s`;Bilibili `?t=<秒>`,**多 P 须带 `p=N`**;本地文件降级为纯文本 `[mm:ss]`;
- frontmatter 必填:`source`、`video_id`(平台 ID,可读)、**`engine_video_id`**(watch-skill 的 `sha256(source)[:16]`,`ask` / `search` 必需)、`author`、`date`、`category`、`type`(操作型/理论型/混合)、`tags`、`duration`、`generated`、**`content_hash`**(见 5.4 重跑保护)、**`degradations`**(降级记录数组);可选 `series`(同系列另建 MOC 笔记);
- 常见坑用 callout(`> [!warning]`);写入调用 obsidian-markdown 技能。

**Bases 兼容性(v3 新增)**:`.base` 是 Obsidian 1.9+ 特性。**阶段 0 preflight 检查用户版本**:不支持则降级为 Dataview 查询块,两者都不可用则生成静态 MOC 笔记 `视频索引.md`(写入时追加一行 wikilink)。

## 5. 处理流程

### 5.0 阶段 0 · 预探测与处理计划(唯一的前置确认点)

1. **Preflight**(一次性,结果缓存):`watch-skill doctor` 通过?vault 路径已固化?Obsidian 版本是否支持 Bases?
2. **元数据探测**:`yt-dlp --skip-download --write-info-json`(或 `watch-skill watch --transcript-only`)取标题、作者、时长、章节、**`language` 字段**、字幕轨语言列表、B 站分 P 信息;
3. **查重**:用 video_id grep vault 内 frontmatter,命中则问"更新 / 跳过 / 另存版本",**禁止静默覆盖**;
4. **分类初判**:先枚举 vault 现有分类目录,只能从中选,或经用户确认新建;
5. **清晰度预判**(v3 修正):标题/简介显示含代码或界面演示,且来源为 B 站非本地文件 → **此处就提示"引擎上限 720p 且不支持登录,如需看清代码请提供本地高清文件"**,而不是等下载后才停(v2 是下载后才发现,浪费一次下载);
6. **打包成一次确认**:分段方案、字幕来源(原生 zh / 原生其他语种 / 本地 whisper 兜底)、抽帧分辨率、预计耗时与 token 量级、是否启用 WebSearch 扩展、**≥20 分钟视频给出章节地图供用户选精看范围**。
   - 注:因本地 whisper 免费,**取消 v2 的"转录费用预估"**,只报"需本地转录,约 N 分钟"。

### 5.1 阶段 1 · 转录优先(v3 重写:两遍法第一遍)

```bash
# 注意:此处【不加 --no-index】—— 这是全流程唯一的索引写入点(见 2.45 陷阱 1)
env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u GEMINI_API_KEY -u OPENROUTER_API_KEY \
  "$WATCH_SKILL_BIN" watch "<source>" --transcript-only --out-dir <work>
```

- 优先级:**原生语言人工字幕 > 原生语言自动字幕 > 本地 faster-whisper > 纯视觉 + 明示局限**;
  引擎的 `_pick_subtitle(original_lang)` 已内建"原生轨优先于机翻轨",skill 只需**核对拿到的轨确实是原生语言**,不符则显式重跑指定 `WATCHSKILL_SUBTITLE_LANGS`;
- 这一遍**不抽帧、通常不下载视频**,成本极低,产出完整带时间戳转录;
- **转录立即存档**到 `<work>/transcript.md`,并在阶段 3 拷入 vault(第 5.5 节的蒸馏前提)。

### 5.2 阶段 2 · 转录驱动的定点抽帧 + 分段理解(v3 重写)

**v2 的盲抽帧问题**:100 帧上限摊到 10 分钟一段 ≈ 6 秒/帧,逐步操作演示极易漏关键步骤。**改为两遍法第二遍**:

1. **cue 时间戳表的生成(v3.1 改为检索驱动)**:阶段 1 已把转录写入索引,主代理对索引做若干语义检索(`watch-skill search` / `ask`)。**查询必须遵守 2.5 的中文词组约定**(空格分隔、3 字以上),典型查询:`操作步骤 点击设置 菜单路径`、`代码示例 终端命令 报错信息`、`图表说明 数据对比`、`注意事项 常见错误 坑点`;命中的 hits 自带时间戳 → 合并去重成 cue 表。**辅以**转录里的指示语("你看这里 / 打开设置 / 输入这个 / 如图")与章节边界作补充,不再以正则为主。
   - 索引不可用(未装 index extra)时降级为纯指示语正则,并记入 `degradations`;
2. 每段派一个 subagent,子代理执行:

```bash
# 注意:此处【必须加 --no-index】—— 否则会清空阶段 1 的全片索引(见 2.45 陷阱 1)
env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u GEMINI_API_KEY -u OPENROUTER_API_KEY \
  "$WATCH_SKILL_BIN" watch "<source>" --start <t0> --end <t1> \
  --timestamps <该段 cue 时间戳,逗号分隔> \
  --resolution 1280 --max-frames 60 --no-index --out-dir <work>
```

- **cue 帧在引擎内被预留配额、不会被均匀采样挤掉**(`perceive/engine.py:141` `pinned_reasons={"cue"}`,`detail_target = max(0, target - len(cues))`,已源码确认),所以关键步骤有保障,同时总帧数可显著低于盲抽;
- **cue 数必须 ≤ `--max-frames`**:`engine.py:164` 对 cues 做 `_even_sample(cues, cap)`,cue 多于上限会被**抽稀**,等于白定位。cue 多时提高 `--max-frames` 或缩短分段;
- 下载缓存使 各段共用一次下载(`--out-dir` 固定到 `<slug>/work/`);
- 子代理内 `Read` 帧(帧只进子代理上下文,用完即弃),按转写规则产出**纯文本段落笔记** + 该段证据帧路径返回;
- 每个子代理 prompt 携带前段 running summary(术语表 + 进行中主题),保证段间指代连贯;
- **段落笔记立即落盘** `<work>/.drafts/segment-N.md`(注明覆盖时间范围);SKILL.md 开头规定断点续跑:先查 `.drafts/`,只补缺失段;
- **证据帧同步拷入 vault `assets/`**(命名 `mm-ss-描述.jpg`),不等最后,避免与临时目录清理竞态;
- 每段完成向用户输出一行进度。

**分段粒度(v3 放宽)**:采用 cue 驱动后帧数可控,**≤15 分钟的视频允许主会话单遍处理**(不必强开 subagent);>15 分钟按 10~12 分钟分段并派 subagent。token 参考:1280 宽帧约 1.1k token/帧,60 帧 ≈ 6.6 万/段。

**转写规则**(子代理执行):

- 图表 → 数据表或 Mermaid,记录轴、数值、结论;
- 操作画面 → 可复现步骤(菜单路径、点击对象、输入值、预期反馈);
- 代码画面 → 完整转写;**以 OCR 文本与视觉读数交叉校验**,两者冲突时以视觉为准并标注 `[OCR 与画面不一致 @mm:ss]`;两者都不可辨 → **先走免模型回补阶梯**(`watch-skill ask <video_id> "<该处画面上写的是什么>"`,引擎会自动 dense_resample + crop_and_reocr,恢复结果 merge 回索引);仍不可辨才写 `[画面文字不可读 @mm:ss]`,**禁止猜测补全**;
- 讲解/字幕 → 时间戳对齐要点。

### 5.3 阶段 2.5 · 类型判定

全部段落完成后,主代理判定 `type`:

- **操作型**:有可复现的软件/工具操作 → 产出 PLAYBOOK;
- **理论型**:讲原理、观点、方法论 → **不产出 PLAYBOOK**(避免为凑结构编造步骤),以"要点卡 + 自测题"小节并入主笔记;
- **混合型**:PLAYBOOK 只覆盖实际演示的部分。

短视频(<10 分钟且知识点少)允许三层合并为单文件,不建目录三件套。

### 5.4 阶段 3 · 沉淀写入(Obsidian)

1. 基于实际内容**最终确认分类与标题**(与阶段 0 初判不符时此处修正,连同 slug / 是否覆盖一并确认——第二个也是最后一个**计划内**确认点);
2. 用 `templates/` 填空生成主笔记 /(条件)PLAYBOOK / EXTEND,合并各段草稿,检查段间术语与编号一致;拷入 `transcript.md`;
3. EXTEND 默认精简模式(Claude 自身知识 + 官方文档链接);WebSearch 仅当阶段 0 勾选;所有扩展内容标注 `[扩展]`,与带时间戳的视频原文严格分离;
4. 笔记语言:正文中文,术语/命令/代码保留原文,首次出现给中译;非中文视频的关键论断附原文引述;
5. **重跑保护(v3 修正)**:v2 用"mtime 晚于 generated"判定人工改动**不可靠**(Obsidian 索引与插件都会动 mtime)。改为:写入时把正文内容 hash 存入 frontmatter `content_hash`;重跑时重算现有文件 hash,**不一致即视为人工改动过** → 写 `*.regen.md` 并列出差异由用户裁决,**禁止直接覆盖**;
6. 写入后**必须运行 `scripts/validate.py`** 并贴出结果;
7. 最终回复逐项自报 checklist 完成状态。

### 5.5 阶段 4 · 可选精华蒸馏

- 输入是**阶段 1 的原始转录**(`transcript.md`),不是蒸馏后的笔记——cangjie 的三重验证要求"原文至少 2 处独立佐证",总结性笔记会让验证失效。故 transcript 必须随产出存档;
- 方法论型 → cangjie-skill 蒸馏为技能包;操作型 → PLAYBOOK 固化为项目内 skill;
- 默认不执行,由用户在处理完成后决定。

**清理时序**:证据帧已拷 assets、transcript 已存档、用户无追加问题 → 才允许清理 work dir(引擎自身的下载缓存由其 LRU 管理,不手动删)。

## 6. 质量控制

1. **证据规则**:每个视频知识点必须有语音或画面证据并附时间戳;辨认不清必须标注,禁止猜测;
2. **validate.py 分层规则(v3 修正)** —— v2 的"每条知识点必须以时间戳链接开头"是**全局规则,会逼 Claude 给理论要点和扩展内容编造时间戳**,与"禁止猜测"直接冲突。改为按文件/小节分层:

   | 目标 | 规则 |
   |------|------|
   | 主笔记「视频要点」小节 | 每条**必须**有时间戳链接 |
   | 主笔记「要点卡 / 自测题」小节(理论型) | **不要求**时间戳;要求每条能溯源到某个带时间戳的要点 |
   | PLAYBOOK 步骤 | 每步**必须**有时间戳链接(操作可复现性的机械保障) |
   | EXTEND.md | **禁止**出现时间戳链接;每条**必须**带 `[扩展]` 标记 |
   | 全文 | frontmatter 必填字段齐全;`type` 与实际产出文件一致;assets 引用的图片文件存在;时间戳格式与 URL 锚点合法 |

3. **可复现盲测**(操作型):派一个只读 PLAYBOOK(不给转录与帧)的 subagent 复述操作、列缺失信息;**缺口回补优先走 `watch-skill ask <engine_video_id> "<缺口词组>"`**(注意用 frontmatter 里记录的**引擎 video_id**,即 `sha256(source)[:16]`,不是我们的可读 slug)——命中精确时刻并返回附近帧路径,无需重新下载或转录,且先走免模型阶梯(见 2.4);ask 无法解决时才用 `--timestamps` + `--max-frames 15` 定点重抽(走 subagent),防二次 token 雪崩;
4. **机械保障**:模板锁结构 + validate.py 校验 + checklist 自报,不依赖提示词自觉;
5. **降级透明**:任何降级(字幕缺失走 whisper、纯视觉、720p 上限、跳段、OCR 关闭)写入 frontmatter `degradations` 与文首信息块。

## 7. 错误处理(v3 修正)

| 场景 | 处理 |
|------|------|
| 非英语原生字幕 | 引擎 `_ensure_original_subs` 自动补拉;仍失败则显式设 `WATCHSKILL_SUBTITLE_LANGS` 重跑;再失败走本地 whisper |
| 拿到的是机翻英文轨 | 核对 info.json `language` 后重跑指定原生语种;**不得**用机翻轨当原文 |
| 完全无字幕 | 本地 faster-whisper(无需 key、无 25MB 限制);机器性能不足则提示改用 `--cloud-stt` + key |
| **B 站含代码/界面且非本地文件** | **阶段 0 即提示**:引擎上限 720p 且不支持 cookie/登录,请提供本地高清文件。**不提供 cookie 方案(两个引擎都不支持)** |
| B 站需登录 / 地区限制 | 提示提供本地文件,不绕过 |
| 视频 ≥20 分钟 | 阶段 0 出章节地图,用户选精看范围 |
| 会话中断 | `.drafts/` 断点续跑,只补缺失段 |
| 帧文字不可读 | OCR 文本交叉校验;仍不可读 → `--timestamps` 定点 + `--resolution 1280` 重抽(subagent);仍不可读则标注 |
| 首次运行模型下载失败/超时 | 报告具体缺失模型与手动安装命令;可先用 `--no-ocr` 降级跑通 |
| watch-skill 引擎异常(v1.0.0 过新) | 记录复现命令;必要时按 2.2 退回 claude-video 备选路径 |

## 8. 使用方式与首次体验

**首次准备约 15~25 分钟**(引擎安装 + whisper/OCR 模型下载 + 冒烟测试),README 须明示。

```
> 用 video-distill 把这个视频沉淀成笔记:https://www.bilibili.com/video/BVxxxx
# 阶段0:preflight + 元数据 + 查重 + 计划 → 用户确认一次
# 阶段1:--transcript-only 取原生中文字幕/本地转录(秒级~分钟级)
# 阶段2:从转录定位 cue → --timestamps 定点抽帧,分段 subagent,逐段落盘 + 进度
# 阶段3:分类/覆盖最终确认一次 → 写入 vault + validate
# 之后可追加:
> 把 PLAYBOOK 固化成 skill / 用 cangjie-skill 蒸馏方法论
```

**确认点说明(v3 诚实化)**:计划内确认 2 次(阶段 0、阶段 3),但查重命中、需要新建分类、需要本地高清文件这三种情况会**各追加一次**打断,最坏约 5 次。README 写清,不承诺"只问两次"。

**触发词设计**:description 用差异化意图词并写明负触发——"当用户要把教学视频**整理成笔记 / 沉淀到 Obsidian / 做成操作手册 / 蒸馏知识**时使用;本 skill 通过 Bash 调用 watch-skill CLI 完成观看;**单纯询问视频内容、不需要沉淀笔记时不适用**"。因未安装 watch-skill 插件,不存在与 `watching-videos` 的触发冲突。

## 9. 非目标(YAGNI)

- **不把跨视频语义检索作为交付目标**(笔记本身可 Grep / Bases 检索)。注意与 v3.1 的区别:引擎索引**保持开启**,因为它是段内时刻定位与证据回补的基础设施(见 2.4);跨视频检索只是免费副产品,不为它写流程、不为它做 UI、坏了也不修;
- 不用 THE LOOP、MCP 服务、REST 等 watch-skill 的其余能力;
- 不做自动批量播放列表处理(系列课程仅预留 `series` frontmatter + MOC 约定);
- 不绕过任何平台的登录/版权限制。

## 10. 实施范围

实现物:

1. `.claude/skills/video-distill/SKILL.md`(preflight、五阶段、两遍法与 cue 抽帧、subagent 编排、Obsidian 规范、断点续跑);
2. `templates/` 三件套模板;
3. `scripts/validate.py`(分层校验,约 80 行);
4. `README.md`(watch-skill 引擎安装、extras 选择、环境变量、首次使用预期、claude-video 退路);
5. vault 内 `视频笔记/` 目录约定 + `视频索引.base`(或 Dataview / 静态 MOC 降级)。

前置动作:**用 uv 托管的 CPython 3.11.15 安装,而非系统 Python 3.14**(理由见 2.2 "Python 版本选择";watch-skill 未发布 PyPI,须从仓库安装)→ 装 watch-skill 引擎(不装插件)→ `watch-skill doctor` 确认 ffmpeg / yt-dlp / **deno** 就位 → 解析 `$WATCH_SKILL_BIN` 绝对路径 → 第 3 节**八项**冒烟测试 → 确认目标 vault 与 Obsidian 版本。

**验收**:附录 D.1 的实测样本(无字幕、1440p、中文、13.7 分钟)+ 一个有原生中文字幕的 B 站视频 + 一个英文 YouTube 操作教学视频,各跑通全流程。逐项检查:

1. validate.py 通过;
2. 操作型视频的盲测 subagent 能仅凭 PLAYBOOK 复现操作;
3. **cue 检索确实命中**(检索结果的时间戳分布与人工抽查的关键时刻吻合);
4. **索引未被分段清空**(分段结束后 `search` 命中数与阶段 1 一致);
5. **无云端调用**(全程 stderr 出现 `scene descriptions skipped`,无视觉计费);
6. 产出符合 4.2 / 5 / 6 节要求。

---

## 附录 A · v2 → v3 变更清单

| # | v2 | v3 | 原因 |
|---|----|----|------|
| 1 | 引擎 claude-video | 引擎 watch-skill(仅 CLI) | 原生中文字幕、本地免 key 转录、CJK OCR;源码核对确认 claude-video 的 `--sub-langs "en.*"` 无配置项 |
| 2 | (隐含)自取 vtt 喂给 claude-video,通道未定义 | 引擎内建原生语言字幕获取 | 消除对上游内部实现的 hack 依赖 |
| 3 | B 站清晰度不足 → 请用户给 cookie | → 阶段 0 即要求本地高清文件 | 两个引擎源码均硬性无 cookie 支持,cookie 方案不成立 |
| 4 | 盲抽帧,10 分钟/段 100 帧 | `--transcript-only` → cue → `--timestamps` 两遍法 | 6 秒/帧会漏操作步骤;cue 帧有预留配额,更准且更省 token |
| 5 | 一律分段 + 每段 subagent | ≤15 分钟可单会话 | cue 驱动后帧数可控;减少编排开销 |
| 6 | validate 全局要求时间戳开头 | 按文件/小节分层 | 全局规则会逼 Claude 给理论要点与扩展内容编造时间戳 |
| 7 | mtime 判人工改动 | frontmatter `content_hash` | Obsidian 插件会改 mtime,误报率高 |
| 8 | Whisper 云端 + 25MB 切块 + 费用预估 | 本地 faster-whisper,无上限,取消费用预估 | 引擎内建,免 key |
| 9 | `.base` 直接使用 | preflight 检查版本 + Dataview / 静态 MOC 降级 | Bases 需 Obsidian 1.9+ |
| 10 | 声称 2 个确认点 | 说明最坏 5 次 | 诚实化预期 |
| 11 | — | subagent 内用 CLI 而非 `/watch` 斜杠命令 | subagent 无法调用斜杠命令 |

## 附录 B · v3 → v3.1 变更(索引层)

| # | v3 | v3.1 | 原因 |
|---|----|----|------|
| 1 | 跳过 `index` extra,`--no-index` | 装 `index`,索引开启 | 原判断"索引只服务跨视频检索"错误;它是时刻定位与证据回补的基础设施 |
| 2 | cue 靠指示语正则 | 语义检索为主、正则为辅 | 正则漏召严重;索引 hits 自带时间戳 |
| 3 | 画面不可读直接标注 | 先走 `ask` 的免模型阶梯(dense_resample → crop_and_reocr) | 两步都无模型调用,恢复结果还会 merge 回索引 |
| 4 | 盲测缺口靠定点重抽 | 优先 `ask`,重抽兜底 | 免重下载、免重转录 |
| 5 | — | 新增 `WATCHSKILL_COST_POLICY=offline_only` | `ask` 阶梯末端可能调云端视觉,须锁死 |
| 6 | — | 明确"不更换嵌入模型" | 默认已多语言;bge-m3/e5-large 1024+ 维 >2GB,换了只对新索引生效 |
| 7 | 非目标含"不做跨视频检索(关索引)" | 改为"不作为交付目标(但索引开启)" | 区分"不用这个功能"与"不装这个组件" |

## 附录 C · v3.1 → v3.2 变更(中文检索)

| # | 变更 | 原因 |
|---|------|------|
| 1 | 新增 2.5 节:定位中文检索缺陷在**查询侧**而非索引侧 | `_fts_query` 与 `lexical_anchor` 均按空白切分,中文整句退化成单 token |
| 2 | 采用查询侧"空格分隔 3 字以上中文词组"约定 | 同时修复 FTS 半边退化(0.45 权重白扔)与 anchor 恒为 0(权重 0.3) |
| 3 | 指出中文提问会**过度升级** ladder,多耗算力 | `lexical_anchor` 权重 0.3,anchor=0 直接压低 `retrieval_confidence` |
| 4 | 5.2 cue 检索查询改写为词组形式 | 落实 2.5 约定 |
| 5 | 冒烟测试新增第 6 项:中文查询 A/B 验证 | 约定需实测确认,不凭推理写死 |
| 6 | 记录备选补救 B(CJK 二元滑窗补丁)与否决 C(ICU / simple 分词器) | B 不触发索引迁移故可行;C 须重建索引且跨平台成本高 |

## 附录 D · v3.2 → v3.3 变更 + 实测记录

### D.1 实测样本

- URL:`https://www.youtube.com/watch?v=LNH4I47ufLk`
- 标题:真人短剧从剧本到成片全自动智能体 低成本 LTX2.3 多图参考V2版本 / 作者:AI代码侠土豆
- 时长 **821s(13.7 分钟)**;源分辨率 **2560×1440**;`chapters` 为空

| 探测项 | 实测值 | 对方案的影响 |
|--------|--------|--------------|
| `language` | **`None`** | 引擎的原生语言自动兜底**不触发**;`_pick_subtitle` 退回字母序 → 必须显式配 `SUBTITLE_LANGS=zh.*`(见第 3 节) |
| `subtitles` | **`[]`** | 无人工字幕 |
| `automatic_captions` | **`[]`** | **无任何字幕** → 必走本地 whisper。这正是选 watch-skill 的实证:同一视频在 claude-video 下**必须**有 Groq/OpenAI key 才有转录 |
| 源高度 | **1440p** | 被引擎格式串砍到 720p,与 cookie 无关 → 催生补救 D(见 2.3) |
| yt-dlp 提取 | 报 `No supported JavaScript runtime`(缺 deno) | preflight 必须确认引擎自管的 deno 到位(见第 3 节) |
| `~/.local/bin` | 装 yt-dlp 后**不在 PATH** | 实证了 `$WATCH_SKILL_BIN` 须用绝对路径(见第 3 节) |

**本次未能实测的部分**:沙箱为 Python 3.10,而 watch-skill 要求 **3.11+**,且未发布到 PyPI(须从仓库安装)。故本地 whisper 中文转录、OCR、索引与检索行为**均未实测**,仍待第 3 节冒烟测试在用户机器上验证。

### D.2 变更清单

| # | 变更 | 原因 |
|---|------|------|
| 1 | 新增 2.45 陷阱 1:**阶段 1 带索引、阶段 2 每段 `--no-index`**(与 v3.2 恰好相反) | `_insert_video` 对同 `video_id` 的派生表执行 `DELETE`,而 `video_id=sha256(source)[:16]` 与时间范围无关 → 分段观看会逐段清空索引 |
| 2 | 新增 2.45 陷阱 2:所有调用用 `env -u` 剥除视觉 key | `_maybe_describe_scenes` 每次索引会用 Haiku 描述最多 24 帧,且**不检查 `cost_policy`** → 有 key 即静默付费,CLI 无开关 |
| 3 | 新增补救 D:放宽 720p 上限至 1440p(一行格式串) | 实测源 1440p 被砍到 720p,与 cookie 无关;对"看清代码"收益最大,优先级高于 CJK 分词补丁 |
| 4 | 字幕轨陷阱由"未验证疑虑"升级为**已确认默认情形** | 实测 `language=None` |
| 5 | 新增 deno / JS runtime 依赖说明 | 实测 yt-dlp 缺 deno 时 YouTube 提取降级 |
| 6 | 所有命令改用 `$WATCH_SKILL_BIN` 绝对路径 | 实测 `~/.local/bin` 不在 PATH;subagent 更不保证继承 |
| 7 | cue 数须 ≤ `--max-frames` | `engine.py:164` 对 cues 做 `_even_sample(cues, cap)`,超量会被抽稀 |
| 8 | frontmatter 增 `engine_video_id`;`ask`/`search` 用它 | 引擎 id 是 source 的 sha256,与我们的可读 slug 不同 |
| 9 | 冒烟测试由 5 项扩为 8 项(含索引不被清空、中文查询 A/B、静默付费验证) | 三条新发现都必须机械验证,不能靠推理 |
| 10 | 确认"cue 帧被预留配额"在 watch-skill 中同样成立 | `perceive/engine.py:141` `pinned_reasons={"cue"}`;此前是从 claude-video 推断的未验证断言 |
