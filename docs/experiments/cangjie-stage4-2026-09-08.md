# cangjie-skill 首次实测（阶段 4 方法论蒸馏路线）：2026-09-08

**问的问题**：video-distill 阶段 4 的「方法论型 → cangjie-skill 蒸馏成技能包」这条路，真实跑一次通不通？
这是「视频知识沉淀成指导工作的 skill」链路上唯一从未验证的一段。

**安装状态修正**：此前实验记录称 cangjie「本机未装」——不准确。磁盘上 `~/.claude/skills/cangjie-skill`
已有 8/1 的 clone（55e4b70），本次更新到上游 HEAD 34e34bc（v2.5.0，2026-09-04）。准确说法是：
**已安装但从未实测、未进过任何会话的可用 skill 清单**。

## 一、结果总览

| 环节 | 结果 |
|---|---|
| 脚本依赖 | ⚠️ 系统无 PyYAML ⇒ `cangjie.py` 直接 ImportError；**doctor 在系统 python 下不可达**（import 即崩，自检到不了场）。解法：watch-skill venv 的 python 自带 yaml 6.0.3，零安装借用 |
| 输入 | 全新真实材料：9/7 发布的 H3 实测视频 transcript（video-distill 路径 B 当日产出，393 行） |
| 阶段 0 | BOOK_OVERVIEW 完成（自主确认留痕）；如实标注「实测评测、方法论成分稀薄」 |
| 阶段 1 | 5 个并行 extractor（Agent 工具一次发起），候选 10 框架+11 原则+8 案例+8 反例+15 术语；弱置信候选如实标注；无索引按规程回退全量扫描 |
| 阶段 1.5 | **21 条技能候选 → 4 条通过（19%）**，17 条淘汰全部写 rejected/ 附原因 |
| 阶段 1.6 | 4 promoted + 1 路由入口 = 5 可发现入口 ≤ 预算 8 |
| 阶段 2/3 | 4 张 RIA 六段能力卡 + verified.yaml（Bundle）+ also_read 互链 + GLOSSARY |
| 阶段 4 | 压力测试用例**已设计未执行**（触发 harness 运行属下一阶段，诚实边界） |
| 阶段 5 | **首编被硬闸门拦截**（见下），修复后原子发布 single 产物；`validate_skill_pack.py` 0 errors |

## 二、两个上游发现（都已留档）

1. **脚本依赖未声明**：`cangjie.py` 需要 PyYAML，但 SKILL.md/README 不提、`doctor` 在缺依赖的解释器下
   自己就起不来——和本项目「watch-skill 缺 perceive extra 而 doctor 全 ok」同一形状的问题：
   **自检仪器必须能在仪器本身装不起来的环境里说话，否则等于没有**。
2. **also_read 契约：methodology 文档与编译器不一致**。`03-stage3` 让把能力引用关系写进 also_read
   （schema 未约束格式），我按惯例写 capability_id ⇒ 编译器生成的路由表把它当 slug 拼路径 ⇒
   首编产物 2 处断链，被它自己的 `[hard-gate]` staging 校验**当场拦下、拒绝发布**。
   改成 slug 重编即过。⇒ 闸门是真的在工作（这个技能最值得肯定的一点）；
   但 id/slug 契约需要上游二选一：要么文档改示例，要么编译器做 id→slug 映射。

## 三、三重验证是真实的质量门（不是装饰）

最有说服力的一条淘汰：**「六宫格故事板提示词」**——全片最惊喜结果（六连镜头叙事）的直接成因，
V2/V3 双强，但全片只有泡茶一个故事（n=1），V1 跨域佐证不过 ⇒ 按规则降为 example，
 rejected/ 里写明「捞回条件：作者在第二个故事板案例复用同一声明结构」。

通过率 19%（4/21），落在规程给的「散文类 5–10%」与「方法论密集 30–50%」之间——
对方法论稀薄的实测视频，这个数字本身说明判据没有放水。

## 四、产物

- `video-distill-workspace/cangjie-test/`（gitignore 覆盖，不在仓库）：
  - `books/yt-qesHplS26B8/`：全流水线中间产物（candidates/、rejected/、verified.md、
    DIGEST.md、PIPELINE_STATE.md、pressure-tests.md、.cangjie/ Bundle）
  - `dist/`：编译产物 **minimax-h3-review-lessons**（single 模式：1 入口 SKILL.md +
    路由表 + 4 能力卡 + cheatsheet/glossary/overview + BUILD_MANIFEST）
- 装机：把 dist/ 复制或软链为 `~/.claude/skills/minimax-h3-review-lessons/` 即可
  （warning 会随目录同名消失）；是否装机属用户决策，试点未擅自安装

## 五、诚实的边界

- **触发评测未跑**：阶段 4 的 13 条用例（正向/兄弟诱饵/近邻负向 + router 互斥）只有设计没有执行，
  「装上去会不会被正确触发」仍是未验证项（可用 `trigger_test.py` 的双对照纪律补测）
- **方法论有效性未验证**：四张能力卡的 A2/E 是纸面可执行，「实际帮到一次真实决策」没有发生
- 输入是**混合型**视频（非纯方法论内容）——这恰好测出了判据的严格性，但也意味着
  换一本方法论密集的「书」，通过率与产物形态可能很不同（n=1）
- 单编 single 模式；pack 模式（5 入口）未编译对比

## 六、对「阶段 4 能否落地」的回答

**能落地，且两条路线如今都有一次实测**：操作型 → PLAYBOOK（video-distill 已闭环）；
方法论型 → cangjie-skill（本次闭环，到编译发布为止）。链路上仍缺的是最后一环：
**装机后的触发与使用验证**（触发测试 + 真实用例）——那是下一步，不是本试点的范围。
