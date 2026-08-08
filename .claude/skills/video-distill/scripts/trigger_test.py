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
    a = ap.parse_args()

    items = CONTROLS + json.loads(Path(a.eval_set).read_text(encoding="utf-8"))
    out = Path(a.out)
    out.write_text("", encoding="utf-8")

    rows = []
    for i, it in enumerate(items):
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
