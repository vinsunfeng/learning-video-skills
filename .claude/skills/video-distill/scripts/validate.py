#!/usr/bin/env python3
"""校验 video-distill 产出的笔记目录。

分层校验，而不是全局规则。为什么分层：如果对每一行都要求时间戳，理论型视频的
「要点卡」和 EXTEND 里的扩展内容就会被逼出编造的时间戳——那与「禁止猜测」直接
冲突。所以按文件和小节分别定规则：视频原文必须可追溯，扩展内容必须不可混淆。

用法：
    python3 validate.py <笔记目录>
    python3 validate.py <笔记目录> --json

退出码：0 全部通过；1 有 ERROR；WARN 不影响退出码。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REQUIRED_FRONTMATTER = [
    "source", "video_id", "engine_video_id", "author", "category",
    "type", "tags", "duration", "generated", "content_hash", "degradations",
]
VALID_TYPES = {"操作型", "理论型", "混合"}

# 时间戳锚点。标签可以是单点 [01:23] 也可以是区间 [01:23–02:05]（区间对操作步骤更贴切，
# 一个步骤本来就跨一段时间），但**必须是 markdown 链接**——可点击才是能回查的凭据。
# 全角括号 〔01:23〕 不是链接，不接受。
_TS = r"\d{1,2}:\d{2}(?::\d{2})?"
TS_LINK = re.compile(rf"\[{_TS}(?:\s*[–\-~至]\s*{_TS})?\]\([^)]+\)")
# 本地文件没有可跳转 URL，降级为纯文本形式
TS_PLAIN = re.compile(rf"\[{_TS}(?:\s*[–\-~至]\s*{_TS})?\]")
# 常见的错误写法，报错时直接指出来，比「缺时间戳」有用得多
TS_WRONG = re.compile(rf"[〔【（]\s*{_TS}(?:\s*[–\-~至]\s*{_TS})?\s*[〕】）]")
# 要点条目须以时间戳开头。容忍列表符号、序号、以及少量强调标记，
# 但时间戳必须在实质内容之前——它是这条要点的凭据，不是句中的补充说明。
_TS_ANY = rf"(?:\[{_TS}(?:\s*[–\-~至]\s*{_TS})?\](?:\([^)]+\))?)"
TS_AT_START = re.compile(rf"^(?:[-*+]\s+|\d+\.\s+)?(?:\*{{1,2}})?{_TS_ANY}")
IMG_EMBED = re.compile(r"!\[\[([^\]]+?)\]\]")
UNFILLED = re.compile(r"\{\{[^}]+\}\}")


class Report:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, level: str, check: str, msg: str, where: str = "") -> None:
        self.items.append({"level": level, "check": check, "message": msg, "where": where})

    def error(self, check: str, msg: str, where: str = "") -> None:
        self.add("ERROR", check, msg, where)

    def warn(self, check: str, msg: str, where: str = "") -> None:
        self.add("WARN", check, msg, where)

    def ok(self, check: str, msg: str = "", where: str = "") -> None:
        self.add("OK", check, msg, where)

    @property
    def failed(self) -> bool:
        return any(i["level"] == "ERROR" for i in self.items)


def split_frontmatter(text: str) -> tuple[dict, str]:
    """极简 YAML 前置块解析——只需要顶层标量与列表，不引入 pyyaml 依赖。

    必须处理块列表形式，否则会误报字段缺失：

        degradations:
          - 无字幕轨，走本地 whisper
          - 源 1440p 被降采样到 720p

    顶层键的值是空的，真正内容在缩进的 `-` 行里。早期版本只读行内值，
    于是把这种（完全合法且更常用的）写法判成「缺失」——裁判自己出错比不校验更糟。
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw, body = text[3:end], text[end + 4:]
    fm: dict = {}
    cur: str | None = None
    for line in raw.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        # 缩进的列表项 / 续行 → 归属上一个键
        if line.startswith((" ", "\t", "-")):
            if cur is not None:
                fm[cur] = (fm.get(cur, "") + " " + line.strip().lstrip("- ")).strip()
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        cur = k.strip()
        fm[cur] = v.strip().strip('"').strip("'")
    return fm, body


def sections(body: str) -> dict[str, str]:
    """按二级标题切分正文。"""
    out: dict[str, str] = {}
    cur = "_preamble"
    buf: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            out[cur] = "\n".join(buf)
            cur = line[3:].strip()
            buf = []
        else:
            buf.append(line)
    out[cur] = "\n".join(buf)
    return out


def bullet_lines(text: str) -> list[str]:
    """正文条目行，跳过注释、表格、代码块。

    2026-08-08 修：原来只跳过**以 `<!--` 开头的那一行**，
    多行注释的内部行会漏进来。而 `EXTEND.md` 模板自带的注释里
    正好有一个编号列表 ⇒ **任何保留模板注释的笔记都被误判不通过**。
    实测：剥掉注释后同一份笔记从「1/6 条缺标记」变成「4 条全部合规」。

    > docstring 当时已经写着「跳过注释」—— **它承诺了代码没做的事。**
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)   # 先整块剥掉注释
    lines, in_code = [], False
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not s:
            continue
        if s.startswith("<!--") or s.startswith("|") or s.startswith(">"):
            continue
        if s.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+\.\s", s):
            lines.append(s)
    return lines


def md_files(d: Path) -> list[Path]:
    """目录下的笔记文件 —— **跳过 AppleDouble 与隐藏文件**。

    2026-08-08 实测：笔记目录经 macOS `tar` 搬到别的机器后，
    多出 `._EXTEND.md` 这类 **AppleDouble** 伴生文件。
    它们匹配 `*.md`，内容是二进制 ⇒ 校验器直接抛
    `UnicodeDecodeError` 的 traceback。

    > **一个把 traceback 甩给用户的校验器，等于没有校验器** ——
    > 他不知道是自己的笔记坏了，还是工具坏了。

    经 tar / zip / U 盘 / iCloud 搬运是常态，不是异常。
    """
    return [f for f in sorted(d.glob("*.md")) if not f.name.startswith("._")]


def read_md(path: Path) -> str:
    """读笔记文本。**解码失败要说人话，不要抛 traceback。**"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise SystemExit(
            f"✗ 读不了 {path.name}：不是 UTF-8 文本（{e.reason} @ 字节 {e.start}）。\n"
            f"  常见原因：AppleDouble 伴生文件（`._*`）、二进制文件被误放进笔记目录、"
            f"或文件用了 GBK/Big5 编码。\n"
            f"  先确认这个文件该不该在这里；确实是笔记就转成 UTF-8。"
        ) from None


def check_unfilled(rep: Report, name: str, text: str) -> None:
    holes = UNFILLED.findall(text)
    if holes:
        rep.error("模板占位未填写", f"残留 {len(holes)} 处：{holes[:3]}", name)


def check_main_note(rep: Report, path: Path) -> dict:
    text = read_md(path)
    fm, body = split_frontmatter(text)
    name = path.name

    check_unfilled(rep, name, text)

    missing = [k for k in REQUIRED_FRONTMATTER if k not in fm or fm[k] == ""]
    if missing:
        rep.error("frontmatter 必填字段", f"缺失：{', '.join(missing)}", name)
    else:
        rep.ok("frontmatter 必填字段")

    # engine_video_id 此前只查「存在且非空」，填任意字符串都能过闸 —— 那让「机械契约」
    # 的承诺落空。它的定义是 sha256(source.strip())[:16]，而 source 就在同一份
    # frontmatter 里，所以这是可以真正验证的，不必只做存在性检查。
    eid = fm.get("engine_video_id", "").strip().strip('"').strip("'")
    src = fm.get("source", "").strip().strip('"').strip("'")
    if eid:
        if not re.fullmatch(r"[0-9a-f]{16}", eid):
            rep.error("engine_video_id 形式", f"应为 16 位十六进制，实际 '{eid}'", name)
        elif src:
            expect = hashlib.sha256(src.strip().encode("utf-8")).hexdigest()[:16]
            if eid != expect:
                rep.error(
                    "engine_video_id 与 source 匹配",
                    f"由 source 算出应为 {expect}，实际 {eid}"
                    "——两者不符时 ask/search 会查不到这个视频",
                    name,
                )
            else:
                rep.ok("engine_video_id 与 source 匹配")

    t = fm.get("type", "")
    if t and t not in VALID_TYPES:
        rep.error("type 取值", f"'{t}' 不在 {VALID_TYPES}", name)

    secs = sections(body)

    # 视频要点：每条必须以时间戳开头。这是整份笔记可回查性的凭据。
    key = next((k for k in secs if "视频要点" in k), None)
    if key is None:
        rep.error("视频要点小节", "未找到「## 视频要点」", name)
    else:
        items = bullet_lines(secs[key])
        if not items:
            rep.error("视频要点小节", "小节为空", name)
        # 锚定行首而不是「前 80 字符内出现」。窗口写法有个隐含长度限制：
        # 实测一条锚点（长视频 ID + hh:mm:ss 区间）已占 65 字符，只剩 15 余量，
        # 合法写法会被误判。锚定行首没有这个问题，而且与模板的示例一致。
        bad = [b for b in items if not TS_AT_START.match(b)]
        if bad:
            hint = ""
            if any(TS_WRONG.search(b) for b in bad):
                hint = "；检测到全角括号写法（如〔01:23〕），那不是链接，改成 [01:23](url&t=83s)"
            rep.error(
                "要点须带时间戳",
                f"{len(bad)}/{len(items)} 条未以时间戳开头，例：{bad[0][:60]}{hint}",
                name,
            )
        else:
            rep.ok("要点须带时间戳", f"{len(items)} 条全部合规")

    # 要点卡/自测：明确不要求时间戳，反过来提醒不要硬塞
    card = next((k for k in secs if "要点卡" in k or "自测" in k), None)
    if card and t == "理论型" and not bullet_lines(secs[card]) and "|" not in secs[card]:
        rep.warn("理论型要点卡", "理论型视频建议填写要点卡与自测题", name)

    # 未读清的标注是允许的，但要有正确格式
    for m in re.finditer(r"\[画面文字不可读[^\]]*\]", body):
        if "@" not in m.group(0):
            rep.warn("不可读标注格式", f"建议写成 [画面文字不可读 @mm:ss]：{m.group(0)}", name)

    return fm


def check_playbook(rep: Report, path: Path) -> None:
    text = read_md(path)
    _fm, body = split_frontmatter(text)
    name = path.name
    check_unfilled(rep, name, text)

    # 只在「操作步骤」这一节里找步骤。此前对全文无差别 split("### ")，
    # 于是「## 验证」下的 `### 渲染前自查` 也被当成操作步骤要求时间戳 ——
    # 实测把一份手册里最有价值的一节（唯一能在花钱渲染前拦住参数放反的检查）
    # 逼成了加粗行。校验器不该改坏它要保护的东西。
    m = re.search(r"^## 操作步骤\s*$(.*?)(?=^## |\Z)", body, flags=re.M | re.S)
    scope = m.group(1) if m else body
    if not m:
        rep.warn("操作步骤小节", "未找到「## 操作步骤」，退化为全文扫描 ### 标题", name)

    steps = re.findall(r"^### .+?$", scope, flags=re.M)
    if not steps:
        rep.error("PLAYBOOK 步骤", "未找到任何 ### 步骤标题", name)
        return

    # 每个步骤块内必须出现时间戳：操作手册最易错的是顺序与参数，
    # 能跳回原片是唯一的纠错手段。
    blocks = re.split(r"^### ", scope, flags=re.M)[1:]
    missing = [b.splitlines()[0].strip() for b in blocks
               if not (TS_LINK.search(b) or TS_PLAIN.search(b))]
    if missing:
        hint = ""
        if any(TS_WRONG.search(b) for b in blocks):
            hint = "；检测到全角括号写法，那不可点击，改成 [02:38–02:51](url&t=158s)"
        rep.error("步骤须带时间戳", f"{len(missing)} 步缺时间戳：{missing[:3]}{hint}", name)
    else:
        rep.ok("步骤须带时间戳", f"{len(blocks)} 步全部合规")

    if "## 前置条件" not in body:
        rep.warn("前置条件", "缺少「## 前置条件」——盲测最常暴露的缺口", name)
    if "## 验证" not in body:
        rep.warn("验证小节", "缺少「## 验证」，读者无法确认做对了", name)


def check_extend(rep: Report, path: Path) -> None:
    text = read_md(path)
    _fm, body = split_frontmatter(text)
    name = path.name
    check_unfilled(rep, name, text)

    # 时间戳出现在 EXTEND 里 = 视频原文混进了扩展层，来源就不可分辨了
    stray = TS_LINK.findall(body)
    if stray:
        rep.error(
            "扩展层禁止时间戳",
            f"出现 {len(stray)} 处时间戳链接（{stray[:3]}）——视频原文应留在主笔记",
            name,
        )
    else:
        rep.ok("扩展层禁止时间戳")

    items = bullet_lines(body)
    unmarked = [b for b in items if "[扩展]" not in b]
    if unmarked:
        rep.error(
            "扩展条目须标记",
            f"{len(unmarked)}/{len(items)} 条缺 [扩展] 标记，例：{unmarked[0][:60]}",
            name,
        )
    elif items:
        rep.ok("扩展条目须标记", f"{len(items)} 条全部合规")


def check_type_consistency(rep: Report, fm: dict, d: Path) -> None:
    t = fm.get("type", "")
    has_pb = (d / "PLAYBOOK.md").exists()
    if t == "操作型" and not has_pb:
        rep.error("type 与产出一致", "标为操作型却没有 PLAYBOOK.md", d.name)
    elif t == "理论型" and has_pb:
        rep.error(
            "type 与产出一致",
            "标为理论型却产出了 PLAYBOOK.md——理论型不应为凑结构编造操作步骤",
            d.name,
        )
    else:
        rep.ok("type 与产出一致")


def check_assets(rep: Report, d: Path, fm: dict | None = None) -> None:
    missing = []
    for md in md_files(d):
        for ref in IMG_EMBED.findall(read_md(md)):
            target = ref.split("|")[0].strip()
            if target.startswith("assets/") and not (d / target).exists():
                missing.append(f"{md.name} → {target}")
    if missing:
        rep.error("引用的图片存在", f"{len(missing)} 处失效：{missing[:3]}")
    else:
        rep.ok("引用的图片存在")

    # ── 2026-08-08 新增：一张图都不引用时，上面那条会「通过」──
    #
    # 实测暴露的盲区：Hermes 跑完真实教学视频，产出 0 错误 0 提醒，
    # 而 `assets/` 里 **0 张证据帧** —— 它整份笔记只用了字幕，从没看画面。
    # 「引用的图片存在」在**没有引用**时当然成立。
    #
    # > **一条只在有输入时才检查的规则，等于允许「没有输入」。**
    #
    # 为什么这对操作型笔记是硬错误：专名、命令、参数值以 OCR 为准 ——
    # 声学/字幕解决不了同音与 URL。那次的 PLAYBOOK 里
    # Triton 的 wheel 地址只能写成 `<triton-wheel-url>` 占位符，
    # **正是没看画面的直接后果**。
    frames = sorted((d / "assets").glob("*.jpg")) if (d / "assets").is_dir() else []
    refs = [r for md in md_files(d)
            for r in IMG_EMBED.findall(read_md(md))
            if r.split("|")[0].strip().startswith("assets/")]
    if refs:
        rep.ok("证据帧非空", f"{len(refs)} 处引用、{len(frames)} 个文件")
    elif (fm or {}).get("type", "") == "理论型":
        # 理论型只讲原理，可以没有画面证据 —— 但要说出来，不是默认放过
        rep.warn("证据帧非空", "理论型笔记无证据帧，可接受；若视频有图表演示则应补")
    else:
        rep.error(
            "证据帧非空",
            "0 处画面引用 —— 操作型笔记必须有证据帧。"
            "专名/命令/参数值以 OCR 为准，纯字幕产出的步骤不可复现；"
            "确实无法抽帧就把它写进 frontmatter 的 degradations",
        )


def check_content_hash(rep: Report, d: Path, allow_edited: bool = False) -> None:
    """content_hash 必须可复现 = sha256(正文.strip())[:16]，正文不含 frontmatter。

    默认 **ERROR**。阶段 3 写完就跑校验，此时对不上只有一个原因：算错了 ——
    而算错就意味着重跑保护永远误报「被改过」，保护机制自我失效。此前记为 WARN，
    等于闸门宣称的强度高于实际，比没有闸门更危险。

    `--allow-edited` 降级为 WARN：用于校验一份**事后被人工编辑过**的笔记，
    那种场景下不一致是预期状态（也正是重跑保护要检测的信号）。
    """
    for md in md_files(d):
        if md.name == "transcript.md":
            continue
        fm, body = split_frontmatter(read_md(md))
        stored = fm.get("content_hash", "").strip().strip('"').strip("'")
        if not stored:
            continue
        actual = hashlib.sha256(body.strip().encode("utf-8")).hexdigest()[:16]
        if stored == actual:
            rep.ok("content_hash 可复现", "", md.name)
        elif allow_edited:
            rep.warn("content_hash 一致", f"存储 {stored} ≠ 实际 {actual}——文件被人工改过", md.name)
        else:
            rep.error(
                "content_hash 可复现",
                f"存储 {stored} ≠ 实际 {actual}"
                "——算法是 sha256(frontmatter 之后正文.strip())[:16]；"
                "若这份笔记确实被人工编辑过，用 --allow-edited",
                md.name,
            )


def main() -> int:
    ap = argparse.ArgumentParser(description="校验 video-distill 笔记目录")
    ap.add_argument("note_dir", help="笔记目录，如 <vault>/视频笔记/编程开发/yt-xxx")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument(
        "--allow-edited",
        action="store_true",
        help="把 content_hash 不一致降级为提醒。用于校验事后被人工编辑过的笔记；"
        "刚生成的笔记不要加这个开关，那种情况下不一致就是算错了。",
    )
    args = ap.parse_args()

    d = Path(args.note_dir).expanduser().resolve()
    rep = Report()

    if not d.is_dir():
        print(f"目录不存在：{d}", file=sys.stderr)
        return 2

    reserved = {"PLAYBOOK.md", "EXTEND.md", "transcript.md"}
    mains = [p for p in md_files(d) if p.name not in reserved]
    if len(mains) != 1:
        rep.error("主笔记唯一", f"期望 1 个主笔记，实际 {len(mains)} 个：{[p.name for p in mains]}")
        fm = {}
    else:
        fm = check_main_note(rep, mains[0])

    if (d / "PLAYBOOK.md").exists():
        check_playbook(rep, d / "PLAYBOOK.md")
    if (d / "EXTEND.md").exists():
        check_extend(rep, d / "EXTEND.md")
    if not (d / "transcript.md").exists():
        rep.warn("转录存档", "缺 transcript.md——阶段 4 蒸馏需要原始转录，且清理 work dir 后不可恢复")

    if fm:
        check_type_consistency(rep, fm, d)
    check_assets(rep, d, fm)
    check_content_hash(rep, d, allow_edited=args.allow_edited)

    if args.json:
        print(json.dumps({"dir": str(d), "passed": not rep.failed, "items": rep.items},
                         ensure_ascii=False, indent=2))
        return 1 if rep.failed else 0

    icon = {"OK": "✓", "WARN": "!", "ERROR": "✗"}
    for it in rep.items:
        where = f" [{it['where']}]" if it["where"] else ""
        msg = f" — {it['message']}" if it["message"] else ""
        print(f"{icon[it['level']]} {it['check']}{where}{msg}")

    n_err = sum(1 for i in rep.items if i["level"] == "ERROR")
    n_warn = sum(1 for i in rep.items if i["level"] == "WARN")
    print(f"\n{'不通过' if rep.failed else '通过'}：{n_err} 个错误，{n_warn} 个提醒")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
