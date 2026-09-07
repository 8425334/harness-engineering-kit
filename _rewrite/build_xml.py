#!/usr/bin/env python3
"""Convert _rewrite/FINAL.md into a Feishu Docx XML body payload.

Handles the Markdown subset actually used in the article:
headings (#..####), paragraphs with **bold**/`code`, ul/ol lists,
tables, fenced code blocks, and '>' blockquotes. Escapes XML in text.
Embeds preserved Feishu images by existing media token at anchor positions.
"""
import re, sys

SRC = "_rewrite/FINAL.md"
OUT = "_rewrite/article_final.xml"

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def inline(s):
    """Bold then code. Order b(...)code conforms to a>b>em>del>u>code nesting."""
    parts = re.split(r"(\*\*.+?\*\*)", s, flags=re.S)
    out = []
    for p in parts:
        if p.startswith("**") and p.endswith("**") and len(p) >= 4:
            inner = p[2:-2]
            inner = inline_code(inner)
            out.append(f"<b>{inner}</b>")
        else:
            out.append(inline_code(p))
    return "".join(out)

def inline_code(s):
    parts = re.split(r"(`[^`]+`)", s)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) >= 2:
            out.append(f"<code>{esc(p[1:-1])}</code>")
        else:
            out.append(esc(p))
    return "".join(out)

def cell_inline(s):
    return inline(s)

def parse_table(lines):
    # lines: header, separator, body rows. returns xml
    def split_row(l):
        l = l.strip()
        if l.startswith("|"):
            l = l[1:]
        if l.endswith("|"):
            l = l[:-1]
        return [c.strip() for c in l.split("|")]
    header = split_row(lines[0])
    rows = [split_row(l) for l in lines[2:]]
    thead = "<thead><tr>" + "".join(f"<th>{cell_inline(h)}</th>" for h in header) + "</tr></thead>"
    tb = []
    for r in rows:
        tb.append("<tr>" + "".join(f"<td>{cell_inline(c)}</td>" for c in r) + "</tr>")
    tbody = "<tbody>" + "".join(tb) + "</tbody>"
    return f"<table>{thead}{tbody}</table>"

# images to drop-in when an ASCII diagram is encountered
ASCII_REPLACE = {
    "adapter   (REST / RPC / 事件 / 定时": ('<img src="T8Zib9QQvo2JwVxvnNKc2OqJnqb" width="760" name="12-backend-layers.png"/>'),
    "视图层（页面 / 组件）": ('<img src="Wy2PbqhPGokdocxKzlQc8OcMnOb" width="760" name="11-frontend-layers.png"/>'),
}

# (anchor_substring, img) inserted AFTER the block whose raw text contains anchor
INSERTS = [
    ("完整链路是：文档 / 代码 / 用户需求", '<img src="P7yWbmazooeGwqxzPCocLJCHnwc" width="760" name="14-embedding-transformer.png"/>'),
    ("能力很强但不懂项目管理的工程师", '<img src="JWrkbfvuto7Z2xxEXNLcXSAknyd" width="760" name="13-llm-to-harness.png"/>'),
    ("照着字段往下写", '<img src="JqlVbfL2Xo6OigxTS8Oc0HnrnVe" width="760" name="02-linear-impl.png"/>'),
    ("按后端 RAM 的方法", '<img src="CDO8bAA5somfUkxrF7KcFcs5nsb" width="760" name="03-model-driven.png"/>'),
    ("六、反馈闭环：把错误变成工程的养料", '<img src="ToN0b2UAGo1nu6xdrNKcGxJrntg" width="760" name="04-feedback-loop.png"/>'),
    ("边界意识", '<img src="SIypbbfYCoxwAExFdgGcr9IFnsb" width="760" name="05-discount-flow.png"/>'),
    ("不改核心（开闭原则）", '<img src="TivEbdElcoVty4xwFqDckFSNnTb" width="760" name="06-step6-tasks.png"/>'),
    ("T5 | 单测", '<img src="IE4kbysoCobYcvxcsMKcKdX6nVc" width="760" name="07-businesstype-rules.png"/>'),
    ("Step 9 验证与 Review：门禁 + 证据才算完成", '<img src="Eu3Lbr6MuoB25Qxw4OxcbsDMnAe" width="760" name="08-fitness-pipeline.png"/>'),
]

def main():
    text = open(SRC, encoding="utf-8").read()
    lines = text.split("\n")
    blocks = []   # xml strings
    sigs = []     # raw text signature for each block
    i = 0
    n = len(lines)
    def emit(xml, sig):
        blocks.append(xml)
        sigs.append(sig)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            txt = m.group(2).strip()
            emit(f"<h{lvl}>{inline(txt)}</h{lvl}>", txt)
            i += 1
            continue
        # fenced code
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            j = i + 1
            buf = []
            while j < n and not lines[j].strip().startswith("```"):
                buf.append(lines[j])
                j += 1
            j += 1  # skip closing fence
            code = "\n".join(buf)
            rawfirst = buf[0].strip() if buf else ""
            replaced = None
            for k, img in ASCII_REPLACE.items():
                if k in code:
                    replaced = img
                    break
            if replaced is not None:
                emit(replaced, "")
            else:
                langattr = f' lang="{esc(lang)}"' if lang else ""
                emit(f"<pre{langattr}><code>{esc(code)}</code></pre>", code)
            i = j
            continue
        # table
        if stripped.startswith("|"):
            j = i
            tbl = []
            while j < n and lines[j].strip().startswith("|"):
                tbl.append(lines[j])
                j += 1
            # need at least header + separator
            if len(tbl) >= 2 and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", tbl[1]):
                emit(parse_table(tbl), " ".join(t.strip() for t in tbl))
                i = j
                continue
            else:
                # not a real table; treat as paragraph
                pass
        # blockquote
        if stripped.startswith(">"):
            j = i
            paras = []
            cur = []
            while j < n and lines[j].strip().startswith(">"):
                content = lines[j].strip()[1:]
                if content.strip():
                    cur.append(content.strip())
                elif cur:
                    paras.append(" ".join(cur)); cur = []
                j += 1
            if cur:
                paras.append(" ".join(cur))
            inner = "".join(f"<p>{inline(p)}</p>" for p in paras)
            emit(f"<blockquote>{inner}</blockquote>", " ".join(paras))
            i = j
            continue
        # list item start
        lm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if lm:
            ordered = lm.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items = []
            raw_items = []
            j = i
            while j < n:
                l2 = lines[j]
                lm2 = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", l2) if l2.strip() else None
                if lm2 is None or (lm2.group(1) != lm.group(1)):
                    break
                items.append(lm2.group(3))
                raw_items.append(lm2.group(3))
                j += 1
            li = "".join(f"<li>{inline(it)}</li>" for it in items)
            emit(f"<{tag}>{li}</{tag}>", " ".join(raw_items))
            i = j
            continue
        # horizontal rule
        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", stripped):
            emit("<hr/>", "---")
            i += 1
            continue
        # paragraph: gather until next blank or block marker
        j = i
        para = []
        while j < n:
            l2 = lines[j].strip()
            if not l2:
                break
            if (l2.startswith("#") or l2.startswith("```") or l2.startswith("|")
                    or l2.startswith(">") or re.match(r"^(\s*)([-*]|\d+\.)\s+", l2)
                    or re.match(r"^\s*(-{3,}|\*{3,})\s*$", l2)):
                break
            para.append(l2)
            j += 1
        ptxt = " ".join(para)
        emit(f"<p>{inline(ptxt)}</p>", ptxt)
        i = j

    # inserts: process from last to first so indices stay valid
    for anchor, img in reversed(INSERTS):
        idx = None
        for k, sig in enumerate(sigs):
            if anchor in sig:
                idx = k
                break
        if idx is None:
            print(f"WARN anchor not found: {anchor}", file=sys.stderr)
            continue
        blocks.insert(idx + 1, img)
        sigs.insert(idx + 1, "")

    body = "\n".join(b for b in blocks)
    title = '<title>Harness AI Coding 实战教程</title>'
    open(OUT, "w", encoding="utf-8").write(title + "\n" + body)
    nimg = body.count("<img ")
    print(f"blocks={len(blocks)} bytes={len(body.encode('utf-8'))} images={nimg} -> {OUT}")

if __name__ == "__main__":
    main()
