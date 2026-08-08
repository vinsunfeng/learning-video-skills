#!/usr/bin/env python3
"""blind_prep — 为「可复现盲测」准备一个**看不到答案**的隔离副本。

## 为什么需要这个脚本，而不是口头说「你只看 PLAYBOOK」

2026-08-08 实测出的问题：agent 产出的 PLAYBOOK 通过了 `validate.py`
全部检查（0 错 0 提醒），而里面一条关键命令**抄反了** ——
画面是 `"triton-windows>=3.7,<3.8"`，它写成 `"triton-windows<3.7"`。

> **`validate.py` 能校验结构、时间戳、hash，不能校验你有没有读对画面。**

盲测是唯一能抓住这类错的手段：让一个**没看过视频**的 agent
只凭手册去执行，它卡在哪里，就是手册缺哪里。

而盲测要成立，**必须真的看不到答案**。同目录下放着 `transcript.md`
和 `assets/*.jpg`，等于把答案摊在桌上 ——
**一个能偷看的盲测，测的是偷看能力。**

## 用法

    python3 blind_prep.py <笔记目录> <输出目录>
    # 然后把输出目录交给一个干净的 subagent，附上它打印的提示词

## 做了什么

1. **只复制 `PLAYBOOK.md`** —— 不带主笔记、不带 transcript、不带 assets
2. **把 `![[assets/...]]` 图片嵌入替换成 `[此处原有截图，盲测中已移除]`**
   —— 图片是证据，盲测要测的恰恰是「没有证据帧时手册够不够」
3. 打印一份标准提示词，三个问题都是**可判定的**，不是「你觉得怎么样」
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

IMG = re.compile(r"!\[\[[^\]]*?\]\]")
# 图片下方常跟一行斜体说明，里面带时间戳链接 —— 那也是线索，一并移除
CAPTION = re.compile(r"^\*\[\d{1,2}:\d{2}.*$", re.M)

PROMPT = """你是一个**没有看过这个视频**的执行者。你手上只有一份操作手册：

    {playbook}

请严格按手册执行，并回答三个问题。**不要上网搜索，不要凭已有知识补全** ——
我要测的正是这份手册本身够不够用。

1. **逐步复述**你会实际做的操作。凡是命令行，写出你会**原样输入的字符**。
2. **列出你无法执行的地方**：哪一步缺了必要信息（路径、文件名、版本号、
   下载地址、点击对象、预期反馈），以至于你只能猜。逐条说缺什么。
3. **列出你觉得可疑的地方**：看起来自相矛盾、或者不像真实命令的内容。

对第 2、3 条，宁可多报不要漏报。**报错了没有代价，漏报会让一份坏手册通过。**
"""


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    pb = src / "PLAYBOOK.md"
    if not pb.exists():
        print(f"✗ {src} 里没有 PLAYBOOK.md —— 理论型笔记不需要盲测")
        return 1

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    t = pb.read_text(encoding="utf-8")
    n_img = len(IMG.findall(t))
    t = IMG.sub("[此处原有截图，盲测中已移除]", t)
    t = CAPTION.sub("", t)
    (out / "PLAYBOOK.md").write_text(t, encoding="utf-8")

    leaked = [p.name for p in out.iterdir() if p.name != "PLAYBOOK.md"]
    print(f"✓ 隔离副本：{out / 'PLAYBOOK.md'}")
    print(f"  移除截图 {n_img} 处｜同目录多余文件：{leaked or '无'}")
    print()
    print("─" * 60)
    print(PROMPT.format(playbook=out / "PLAYBOOK.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
