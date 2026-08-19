#!/usr/bin/env python3
"""trigger_test — 量「触发准确性」：该触发时触发吗？不该触发时忍住吗？

## 为什么不用 skill-creator 的 run_loop

skill-creator 的 `scripts/run_loop.py` 是正规工具，但它 shell 出去调 `claude -p`，
而 2026-08-08 本机那个 CLI 的 **OAuth token 已过期（401）** ⇒
每条查询都失败，`triggered` 一律为 False。

**它的失败方式是静默的零** —— 报告照样打出
`[PASS] rate=0/3 expected=False` 和 `[FAIL] rate=0/3 expected=True`，
看起来像「准确率 55%，有待改进」，而真相是**它一次都没测到**。

> **一个所有条目都返回 0 的测试，测不出任何东西** ——
> 而负例会替它伪装成一半是好的。

所以这里换成本机可跑的 agent（Hermes，skill 已装、provider 可用）。

## 为什么用 subprocess 传 argv，而不是写 shell 脚本

我先用 bash 写了两版，都栽在同一件事：**同一条命令前台成功、后台脚本里中文变乱码**，
agent 收到的是 `用户对你说：「��`。
换 locale、加 `< /dev/null`、query 走文件，都没解决。

`subprocess.run([...])` 不经过 shell，**引号、转义、locale 这一整类 bug 直接消失**。

> 跟 shell 引号斗第三回合的时候，应该换掉 shell，而不是加第三个 workaround。

## 必带的两个已知对照

- **正对照**：一句几乎照抄 description 的请求 —— 它必须 TRIGGER
- **负对照**：一句完全无关的请求 —— 它必须 NO_TRIGGER

**任一对照不符 ⇒ 整轮数据作废，先修仪器。**
这条不是形式主义：上面那两次失败，全靠正对照答「乱码」才没被当成真实结论。

## 用法

    python3 trigger_test.py <trigger-evals.json> [--profile wiki] [--out /tmp/trigger.jsonl]
"""
from __future__ import annotations

import argparse
import json
import os
import time
import re
import subprocess
import sys
from pathlib import Path

HERMES = Path.home() / ".local/bin/hermes"

CONTROLS = [
    {"query": "把这个教学视频整理成 obsidian 笔记：https://youtu.be/known-positive",
     "should_trigger": True, "ctl": "正对照"},
    {"query": "帮我写一个 Python 快速排序函数，加上单元测试",
     "should_trigger": False, "ctl": "负对照"},
]

# **问句里必须点名那个 skill。** 2026-08-08 第一版没点名，只问「TRIGGER 或
# NO_TRIGGER」，于是 agent 回答的是「这事要不要用某个技能/工具」——
# 理由里写着「匹配 youtube-content skill」「视频压缩任务，需 ffmpeg 转码」
# 「PDF 转 Obsidian 笔记」。11 条负例误报 7 条，**大半是问句的错，不是 description 的错**。
#
# > **分数会骗人，理由不会。**
# > 只看 8/9 和 4/11，我会去改 description —— 而真正该改的是题目。
TMPL = ("用户对你说：「{q}」\n\n"
        "只判断一件事：**你会不会使用 `{skill}` 这个 skill 来处理它？**\n"
        "别的 skill、别的工具（ffmpeg / 搜索 / 直接回答）都不算。\n"
        "不要执行任何操作、不要调用任何工具。\n"
        "只回一行：TRIGGER 或 NO_TRIGGER，后跟不超过 20 字理由。")


def ask(profile: str, skill: str, query: str, timeout: float = 180.0) -> str:
    p = TMPL.format(q=query, skill=skill)
    try:
        r = subprocess.run(
            [str(HERMES), "-p", profile, "-z", p, "--yolo"],
            capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return "__TIMEOUT__"
    return " ".join((r.stdout + r.stderr).split())[:240]


def ask_claude(skill: str, query: str, timeout: float = 240.0) -> tuple[bool | None, str]:
    """Claude 侧：把**真实的用户原话**发给 `claude -p`，看它是否调用目标 skill。

    ## 为什么这条比「问它会不会用」更硬

    Hermes 侧那条问的是 agent 的**自述**（「你会不会用 X」）。这里读的是
    `stream-json` 里真实的 `tool_use` 事件 —— **行为，不是自述。**

    ## 三个必须做对的细节

    1. **必须核对 skill 名字。** 本机装着 30 多个 skill，
       「出现了 `"name":"Skill"`」只说明触发了*某个* skill。
       实测正例的 input 是 `{"skill": "video-distill", ...}` —— 名字对上才算。
    2. **一检测到就杀进程。** 不杀的话它会真去干活：实测一条正例跑了
       **26 次 Bash**、下载视频、跑 doctor。既慢（75~150s）又有副作用。
    3. **超时返回 None，不是 False。** 读不出结论 ≠ 没触发。
       把超时算成 NO_TRIGGER 会凭空抬高负例分数。

    ## 为什么不用 skill-creator 的官方 harness

    它造一个**合成 command** 放进 `.claude/commands/`，而真实触发走的是
    `~/.claude/skills/` 里的 skill —— 这个 CLI 版本里是两套机制。
    2026-08-08 实测：修掉 401、修掉 description 截断、把默认 30s 超时提到 240s
    之后，**20/20 仍然 `rate=0`**。那是结构性不兼容，不是配置问题。
    """
    claude = Path.home() / ".local/bin/claude"
    cmd = [str(claude), "-p", query, "--output-format", "stream-json",
           "--verbose", "--include-partial-messages"]
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)          # 允许在 claude 里嵌套 claude -p
    env.setdefault("LANG", "en_US.UTF-8")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL, text=True, env=env,
                            cwd=str(Path.home() / "Claude/Projects/video"))
    # ── 只看 Skill 事件**之后**的 input 分片 ──
    #
    # 第一版写的是「见到 Skill 事件后，在整个累积缓冲里找 skill 名」——
    # 而缓冲里早就有 system 事件列出的**全部可用 skill 清单**（本机 30 多个，
    # 含 video-distill）。于是只要触发了*任何一个* skill，名字就「找到了」。
    #
    # 实测后果：「帮我写一个 Python 快速排序函数」被判成触发 video-distill。
    # **负对照当场抓住了它。**
    #
    # > **又一个会自己命中的过滤器。** 今天第三次。
    # > 判据必须锚在「这一次 tool_use 的 input」上，不是「流里出现过这个词」。
    want = re.compile(r'"skill"\s*:\s*"' + re.escape(skill) + r'"')
    t0, in_skill, frag, other = time.time(), False, "", False
    try:
        for line in proc.stdout:                       # type: ignore[union-attr]
            if '"name":"Skill"' in line:
                in_skill, frag = True, ""              # 新的 Skill 调用，清空分片
            if in_skill:
                frag += line
                if want.search(frag):
                    return True, f"Skill tool_use → {skill}"
                # input 结束了还没匹配上 ⇒ 触发的是别的 skill
                if '"type":"content_block_stop"' in line:
                    in_skill, other = False, True
            if time.time() - t0 > timeout:
                return None, "__TIMEOUT__"
    finally:
        proc.kill()                                    # 不杀会真去干活
    return False, "触发了别的 skill" if other else "无 Skill 事件"


def verdict(ans: str) -> bool | None:
    """None = 读不出结论。**读不出不等于没触发** —— 不许当成 NO_TRIGGER。"""
    if "NO_TRIGGER" in ans or "NO TRIGGER" in ans:
        return False
    if "TRIGGER" in ans:
        return True
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="触发准确性（含强制已知对照）")
    ap.add_argument("eval_set")
    ap.add_argument("--profile", default="wiki")
    ap.add_argument("--skill", default="video-distill")
    ap.add_argument("--out", default="/tmp/trigger_test.jsonl")
    ap.add_argument("--backend", choices=["hermes", "claude"], default="hermes",
                    help="hermes = 问自述（快）｜claude = 读真实 tool_use 事件（硬）")
    a = ap.parse_args()

    items = CONTROLS + json.loads(Path(a.eval_set).read_text(encoding="utf-8"))
    out = Path(a.out)
    out.write_text("", encoding="utf-8")

    rows = []
    for i, it in enumerate(items):
        if a.backend == "claude":
            v, ans = ask_claude(a.skill, it["query"])
        else:
            ans = ask(a.profile, a.skill, it["query"])
            v = verdict(ans)
        row = {"i": i, "ctl": it.get("ctl", ""), "expected": it["should_trigger"],
               "got": v, "ok": (v == it["should_trigger"]) if v is not None else None,
               "q": it["query"][:50], "ans": ans[:120]}
        rows.append(row)
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        mark = "✓" if row["ok"] else ("?" if row["ok"] is None else "✗")
        tag = f"[{row['ctl']}]" if row["ctl"] else ""
        print(f"{mark} {i:2d} {tag} 期望={'触发' if it['should_trigger'] else '不触发'} "
              f"实得={row['got']} | {row['q']}", flush=True)

    # ── 先验对照，再谈结果 ──
    ctl = [r for r in rows if r["ctl"]]
    bad = [r for r in ctl if r["ok"] is not True]
    print()
    if bad:
        print("✗✗ 已知对照未通过 ⇒ **本轮数据作废，先修仪器**：")
        for r in bad:
            print(f"   {r['ctl']}：期望 {r['expected']}，实得 {r['got']}｜{r['ans'][:80]}")
        return 2
    print("✓ 两个已知对照都通过，下面的数字才有意义")

    real = [r for r in rows if not r["ctl"]]
    unread = [r for r in real if r["ok"] is None]
    pos = [r for r in real if r["expected"]]
    neg = [r for r in real if not r["expected"]]
    hit = sum(1 for r in pos if r["ok"])
    hold = sum(1 for r in neg if r["ok"])
    print(f"  该触发 {hit}/{len(pos)} 命中（漏触发 {len(pos) - hit}）")
    print(f"  不该触发 {hold}/{len(neg)} 忍住（误触发 {len(neg) - hold}）")
    if unread:
        print(f"  ⚠️ {len(unread)} 条读不出结论 —— **不计入任何一边**，"
              f"把它们算成 NO_TRIGGER 会凭空抬高负例分数")
    for r in real:
        if r["ok"] is False:
            print(f"    ✗ {'漏触发' if r['expected'] else '误触发'}：{r['q']}｜{r['ans'][:70]}")
    return 0 if hit == len(pos) and hold == len(neg) else 1


if __name__ == "__main__":
    sys.exit(main())
