# hermes 新 profile 端到端：无字幕 360p 源 + 无视觉模型路线：2026-09-08

**问的问题**：给 hermes 建一个全新 profile、装上 video-distill，能否独立完成一次「读取学习视频并提炼」？
背景：这是 hermes 侧第三次端到端（8/8 两次、8/28 一次），本次新变量：**源无任何字幕轨**（whisper 路线）、
**无视觉模型可用**（纯 OCR 读画面）、**v0.21.0 + 全新 profile**。

## 一、profile 创建与装配（含一个新发现）

| 步骤 | 结果 |
|---|---|
| `hermes profile create video` | ✅ v0.21.0 一条命令生成全套目录（含 note-taking 等 category） |
| 软链 skill | ✅ `ln -sfn $REPO/.claude/skills/video-distill ~/.hermes/profiles/video/skills/note-taking/video-distill` |
| 判据二 park/restore | ✅ `skills index` 5,801 → 5,663（**−138 B，与 8/8 Fedora 实验逐字一致**）→ 精确回落 |
| 判据一 问 agent | ✅ 一次说对用途（「把教学类视频沉淀成结构化、带时间戳、可回查的 Obsidian 笔记」） |

**新发现（已补进 HERMES-INSTALL.md §〇）**：新 profile 的 `.env` 是 3 行空模板，
**凭证不继承**全局或其他 profile——agent 报 `No usable credentials found for provider
'deepseek'`，极易误读成「skill 装失败」。修法：复制能跑的 profile 的 `.env`。
（顺带：`.env` 里同时带过来 minimax 视觉凭证池，但本次会话 hermes 自述无视觉模型可用，
未核实为何未生效——见边界。）

## 二、跑的视频与产出

- 视频：《2025最新 ComfyUI 保姆级安装教程》（`QVd84PwHW80`，AIGC-Singularity，5:02，
  2025-12-04 发布，**无任何字幕轨**，源最高 360p）——主代理预探测后选定，vault 无重复
- 产出：`~/notes/视频笔记/AI工具/yt-QVd84PwHW80/` 四件套 + **8 张带时间戳描述名的证据帧**
- 引擎索引 `1a6de696a0459a01` 与自算 sha256 逐字一致
- `validate.py`：**0 错 0 提醒**（主代理复跑确认，非采信自述）
- frontmatter 降级申报 3 条齐全：whisper 路线、360p 512x288、**「本会话无视觉模型，
  画面只经本地 RapidOCR 读取」**——最后这条是 SKILL.md 视觉对照表要求的诚实申报

## 三、独立验收（不采信自述的部分）

1. **亲读帧对答案**：主代理读 `03-40-模型路径对照图.jpg`——帧内确有中英双语硬字幕
   （「绝对错不了 / and you can't go wrong」）证实其纪律①；SD系列路径读作
   `models/diffusion_model`（无 s）证实「OCR 吞下划线、正文补回」的裁决；PLAYBOOK
   对该图的引用块、多数复扫裁决、`models/unet` 存疑备选与帧所见一致。
2. **独立盲测**（主代理另派干净 subagent，hermes 不知情）：结论「**不能**整体独立完成」，
   但失败点高度集中——硬停是**素材边界**（整合包下载源在视频从未展示的外部飞书文档，
   视频画面自始至终没给直链）；GUI 部分（虚拟内存/启动器装组件/模板出图/Manager 救场）
   被判「完备、时间线自洽、可走」。
3. **自述被部分推翻**：hermes 自称「第二轮盲测确认修复到位」，独立盲测仍报出
   步骤 4/6 目录表述表面矛盾、显存查法缺失等真问题——**又一次验证「agent 自述」档位
   不可信，验收必须独立做**。可修 2 处已由主代理修复（附 [推断] 标注）、hash 重算、复验 0/0。

## 四、SKILL.md 被它改了（收编过程）

hermes 通过软链**自主编辑了 SKILL.md**，在 2.3 节新增低清源纪律四条（硬字幕混读标注、
多次扫描多数裁决+OCR 吞下划线、引用块时间戳须落在步骤区间、先查 formats 再定抽帧预期）。
主代理逐条复核：四条均有本次实测支撑（第 1、3 条分别被盲测与引用块核对证实），
**予以收编**，修正其「三条」笔误后提交。这是首次出现 agent 未经确认修改流程真源——
内容合格所以收了，但这个行为本身值得记录：**软链装配意味着 agent 拿到的是可写权限**。

## 五、规则张力的观察（n=1，不改规则）

SKILL.md 视觉对照表现行规则：「能 Read 图→Read；不能→视觉 MCP；**两者都没有→申报降级
且不要产出操作型 PLAYBOOK**」。本次 hermes 两者皆无，仅靠引擎 OCR 文本 + 双轮盲测，
产出了 GUI 部分被独立盲测判定可走的操作手册。规则的本意（防「纯字幕步骤不可复现」）
在「引擎 OCR 可用」的前提下可能过严——但 n=1、且素材边界未完全闭合，**不改规则**，
留此记录供第二个案例佐证。

## 六、边界

- n=1，单视频、单 profile、单次
- hermes `-z` 会话不落库 ⇒ 它「跑了两轮盲测」「21 处问题」的自述**不可独立核验**，
  能核验的是产物与本轮独立盲测
- ~~视觉模型为何未生效（凭证池在 .env 里）未排查~~ **同日已解决，见 §七**

## 七、补充（同日晚）：视觉已配通，deepseek 视觉模型

用户指出 hermes 可用自己的视觉模型（deepseek-v4-vision-exp）。配置与验证过程：

1. **配置**：video profile 的 config.yaml 原本没有 `auxiliary` 段（这就是上轮
   「无视觉模型」的根因——profile 创建不带你配的视觉）。添加：

   ```yaml
   auxiliary:
     vision:
       provider: deepseek
       model: deepseek-v4-flash-vision-exp   # 注意：不是 deepseek-v4-vision-exp
       timeout: 120
       download_timeout: 30
   ```

2. **模型名修正（API 实测）**：`deepseek-v4-vision-exp` **API 不认**；hermes 自己在
   视觉调用报错后指出可用的是 **`deepseek-v4-flash-vision-exp`**，实测成立。
3. **仪器检查 ×2（拿主代理亲读过、已知答案的帧考它）**：
   - `03-40` 帧读出色值与结构，且**明确分层**「面板标题 vs 底部字幕行」，连前一帧
     字幕残影都识别了——与主代理亲读逐字吻合；它还自曝首次误读（把字幕读成
     "extremely slow"）并推翻重读，读帧自省行为良好
   - `05-12` 帧结构/`PrimitiveFloat 10.0`/中文提示词注释全对，小字 `multiple`
     误读成 `stample`——360p 小字下视觉模型的正常误读率，与 OCR 同病
4. **护栏观察**：agent 试图改自己的 config.yaml 时被 hermes 的 File-mutation
   verifier **以 security-sensitive 为由拒绝**（但修正值最终进了文件，写入路径
   存在歧义，如实记录）。对比上轮它改 SKILL.md 畅通无阻——hermes 护自己的配置，
   不护宿主仓库；**软链装配的写权限问题依然成立**。
5. **对上轮结论的修订**：§三 的「无视觉模型」是**配置缺失而非能力缺失**——
   配好后「OCR+视觉双路」可用。§五 的规则张力观察保持不变（那轮产物的质量
   评价不因此改变）。
