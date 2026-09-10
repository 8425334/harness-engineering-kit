# -*- coding: utf-8 -*-
"""
Harness Engineering Kit — 全局技术导览（知识分享 PPT）生成脚本
输出: presentations/Harness-Engineering-Kit-全局导览.pptx
设计: 16:9 新势力科技风 —— 深空暗底 + 霓虹高光 + 闪电/速度线；
     主题叙事：AI 正以雷霆之势颠覆传统编码，HEK 让这股力量可控、可批、可验、可审计。
     内容提炼自仓库 core/docs/scripts；全程无终端代码块。
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# ---------------------------------------------------------------- palette (dark neon)
BG       = RGBColor(0x07, 0x0B, 0x16)   # 深空底
BG2      = RGBColor(0x0B, 0x11, 0x20)
PANEL    = RGBColor(0x11, 0x18, 0x2C)   # 卡片面板
PANEL2   = RGBColor(0x17, 0x20, 0x38)   # 芯片/强调面板
BORDER_D = RGBColor(0x28, 0x36, 0x54)
ROW1     = RGBColor(0x0D, 0x13, 0x24)   # 表格奇数行
ROW2     = RGBColor(0x12, 0x1A, 0x2E)   # 表格偶数行

CYAN     = RGBColor(0x00, 0xD9, 0xFF)   # 电流青（主强调）
GREEN    = RGBColor(0x00, 0xFF, 0x9D)   # 霓虹绿
PURPLE   = RGBColor(0x9B, 0x6B, 0xFF)   # 电光紫
PINK     = RGBColor(0xFF, 0x3D, 0x8A)   # 霓虹粉
ORANGE   = RGBColor(0xFF, 0xB0, 0x20)   # 警示橙
RED      = RGBColor(0xFF, 0x5A, 0x5A)

TEXT     = RGBColor(0xE8, 0xEE, 0xF8)   # 正文亮色
MUTED    = RGBColor(0x8A, 0x97, 0xAD)
DIM      = RGBColor(0x5A, 0x66, 0x7E)
WHITE    = RGBColor(0xFF, 0xFF, 0xFF)
DARKTXT  = RGBColor(0x06, 0x0A, 0x14)   # 霓虹底上的深色文字

GREEN_P  = RGBColor(0x0C, 0x24, 0x1F)   # 绿调面板底
AMBER_P  = RGBColor(0x2A, 0x1D, 0x08)   # 橙调面板底
PURPLE_P = RGBColor(0x1B, 0x14, 0x33)   # 紫调面板底
CYAN_P   = RGBColor(0x0A, 0x22, 0x30)   # 青调面板底

FONT   = "Microsoft YaHei"
FONT_M = "Consolas"

EMU_W, EMU_H = Inches(13.333), Inches(7.5)
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "ai-coding-engineering-tutorial")

prs = Presentation()
prs.slide_width, prs.slide_height = EMU_W, EMU_H
BLANK = prs.slide_layouts[6]
PAGENO = [0]

# ---------------------------------------------------------------- helpers
def _apply_font(run, name=FONT, latin=None):
    run.font.name = latin or name
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", name)

def _run(p, text, size=13, bold=False, color=TEXT, name=FONT, italic=False):
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    _apply_font(r, name=name)
    return r

def _alpha(shape, pct):
    solid = shape._element.spPr.find(qn('a:solidFill'))
    if solid is None:
        return
    clr = solid.find(qn('a:srgbClr'))
    if clr is None:
        return
    for old in clr.findall(qn('a:alpha')):
        clr.remove(old)
    el = clr.makeelement(qn('a:alpha'), {'val': str(int(pct * 1000))})
    clr.append(el)

def add_box(slide, x, y, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE, shadow=False, line_w=0.75, adj=None):
    sp = slide.shapes.add_shape(shape, x, y, w, h)
    sp.shadow.inherit = False
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(line_w)
    if adj is not None:
        try: sp.adjustments[0] = adj
        except Exception: pass
    return sp

def txbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf

def para(tf, first=False):
    if first and not tf.paragraphs[0].runs and tf.paragraphs[0].text == "":
        return tf.paragraphs[0]
    return tf.add_paragraph()

def new_slide(bg=BG):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = bg
    return s

def deco(slide):
    """科技感底纹：右上霓虹环 + 右下速度线"""
    r1 = add_box(slide, Inches(11.55), Inches(0.18), Inches(1.55), Inches(1.55), fill=CYAN, shape=MSO_SHAPE.DONUT, adj=0.035)
    _alpha(r1, 8)
    r2 = add_box(slide, Inches(11.98), Inches(0.60), Inches(0.75), Inches(0.75), fill=PURPLE, shape=MSO_SHAPE.DONUT, adj=0.06)
    _alpha(r2, 9)
    for i, (w_, a) in enumerate([(1.5, 15), (1.0, 9), (0.6, 5)]):
        ln = add_box(slide, int(EMU_W - Inches(w_)) - Inches(0.25), Inches(6.60) + Inches(0.13 * i), Inches(w_), Inches(0.035), fill=CYAN)
        _alpha(ln, a)

def bands(slide, items):
    """斜向能量带：items = [(x, y, w, h, color, alpha, rot)]"""
    for bx, by, bw, bh, col, al, rot in items:
        b = add_box(slide, Inches(bx), Inches(by), Inches(bw), Inches(bh), fill=col, shape=MSO_SHAPE.PARALLELOGRAM)
        b.rotation = rot
        _alpha(b, al)

def bolt(slide, x, y, w, h, color=CYAN, alpha=None, glow=True):
    if glow:
        for i in (3, 2, 1):
            pad = Inches(0.15 * i)
            g = add_box(slide, int(x - pad), int(y - pad), int(w + 2 * pad), int(h + 2 * pad), fill=color, shape=MSO_SHAPE.LIGHTNING_BOLT)
            _alpha(g, 16 - 4 * i)
    b = add_box(slide, x, y, w, h, fill=color, shape=MSO_SHAPE.LIGHTNING_BOLT)
    if alpha is not None:
        _alpha(b, alpha)
    return b

def header(slide, kicker, title, color=CYAN, title_size=25):
    deco(slide)
    add_box(slide, Inches(0.55), Inches(0.42), Inches(0.16), Inches(0.46), fill=color, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.5)
    seg = _sec_index(kicker)
    kk = f"{seg + 1:02d} · " + kicker if seg is not None else kicker
    tf = txbox(slide, Inches(0.82), Inches(0.40), Inches(11.0), Inches(0.35))
    p = para(tf, True); _run(p, kk, size=11.5, bold=True, color=color)
    tf = txbox(slide, Inches(0.82), Inches(0.70), Inches(11.9), Inches(0.62))
    p = para(tf, True); _run(p, title, size=title_size, bold=True, color=WHITE)
    add_box(slide, Inches(0.82), Inches(1.34), Inches(0.62), Inches(0.05), fill=color)
    add_box(slide, Inches(1.46), Inches(1.34), Inches(0.28), Inches(0.05), fill=PURPLE if color != PURPLE else CYAN)
    add_box(slide, Inches(1.76), Inches(1.362), Inches(2.0), Inches(0.014), fill=BORDER_D)

SECS = [
    ("WHY",  GREEN,  "开篇·为什么"),
    ("WHAT", CYAN,   "是什么·放什么"),
    ("HOW",  PURPLE, "怎么转·受控变更"),
    ("GROW", PINK,   "怎么长·反哺"),
    ("USE",  ORANGE, "怎么用·落地"),
]
SEC_SYN = {"why": 0, "what": 1, "how": 2, "grow": 3, "use": 4}
def _sec_index(section):
    key = (section or "").lower()
    for k, i in SEC_SYN.items():
        if k in key:
            return i
    return None

def secbar(slide, section):
    """五段章节进度条：告诉受众『现在讲到第几段』，强化结构层次感"""
    idx = _sec_index(section)
    if idx is None:
        return
    n = len(SECS)
    x0, x1, y, gap = Inches(0.55), Inches(12.78), Inches(7.40), Inches(0.06)
    seg = (x1 - x0 - gap * (n - 1)) / n
    for i, (lab, c, name) in enumerate(SECS):
        sh = add_box(slide, int(x0 + int(seg + gap) * i), int(y), int(seg), Inches(0.08),
                     fill=(c if i == idx else BORDER_D), shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.5)
        _alpha(sh, 100 if i == idx else 45)
    label = f"{idx + 1:02d} · {SECS[idx][2]}"
    tf = txbox(slide, Inches(0.80), Inches(7.32), Inches(5.5), Inches(0.16))
    p = para(tf, True); _run(p, label, size=8.5, bold=True, color=SECS[idx][1])

def footer(slide, section, page=None):
    PAGENO[0] += 1
    secbar(slide, section)
    tf = txbox(slide, Inches(0.55), Inches(7.08), Inches(8.5), Inches(0.3))
    p = para(tf, True); _run(p, "Harness Engineering Kit · 全局技术导览", size=9, color=DIM)
    tf = txbox(slide, Inches(9.2), Inches(7.08), Inches(3.58), Inches(0.3))
    p = para(tf, True); p.alignment = PP_ALIGN.RIGHT
    _run(p, f"{section}   |   {page or PAGENO[0]}", size=9, color=DIM)

def bullets(slide, x, y, w, h, items, size=13, gap=6, line_spacing=1.12, color=TEXT, marker=CYAN):
    tf = txbox(slide, x, y, w, h)
    first = True
    for lvl, segs in items:
        p = para(tf, first); first = False
        p.space_after = Pt(gap); p.line_spacing = line_spacing
        if lvl == 0:
            p.space_before = Pt(3)
            _run(p, "▍", size=size - 1, bold=True, color=marker)
        else:
            _run(p, "   – ", size=size - 2, color=MUTED)
        for txt, st in segs:
            _run(p, txt, size=st.get("size", size - (2 if lvl else 0)), bold=st.get("bold", False),
                 color=st.get("color", color), name=st.get("name", FONT), italic=st.get("italic", False))
    return tf

def chips(slide, x, y, w, items, h=0.34, gap=0.14, fill=PANEL2, color=CYAN, size=11, line=BORDER_D):
    cx = x
    for label in items:
        est = 0.30 + 0.145 * len(label)
        box = add_box(slide, cx, y, Inches(est), Inches(h), fill=fill, line=line, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.5, line_w=1.0)
        tf = box.text_frame; tf.word_wrap = False
        tf.margin_left = tf.margin_right = Inches(0.02); tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        _run(p, label, size=size, bold=True, color=color)
        cx += Inches(est) + Inches(gap)
    return cx

def pic_card(slide, path, x, y, max_w, max_h, caption=None):
    from PIL import Image
    im = Image.open(path); iw, ih = im.size
    r = min(max_w / iw, max_h / ih)
    w, h = iw * r, ih * r
    left = x + (max_w - w) / 2
    top = y + (max_h - h) / 2
    pad = Inches(0.1)
    add_box(slide, int(left - pad), int(top - pad), int(w + 2 * pad), int(h + 2 * pad),
            fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.035)
    slide.shapes.add_picture(path, int(left), int(top), int(w), int(h))
    if caption:
        tf = txbox(slide, int(x), int(y + max_h + Inches(0.08)), int(max_w), Inches(0.3))
        p = para(tf, True); p.alignment = PP_ALIGN.CENTER
        _run(p, caption, size=9.5, color=MUTED, italic=True)
    return left, top, w, h

def tagline(slide, text, color=CYAN, y=1.44, h=0.44):
    """页首一句话核心：不全面但一击即中的锚点（置于 header 之下、正文之上）"""
    add_box(slide, Inches(0.62), Inches(y), Inches(12.1), Inches(h), fill=PANEL2, line=color, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14, line_w=1.0)
    add_box(slide, Inches(0.62), Inches(y), Inches(0.07), Inches(h), fill=color, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.5)
    tf = txbox(slide, Inches(0.86), Inches(y), Inches(11.7), Inches(h), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); p.line_spacing = 1.05
    _run(p, "▍ ", size=11, bold=True, color=color)
    _run(p, text, size=11.5, bold=True, color=WHITE)
    return tf

def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text

def num_steps_v(slide, x, y, w, steps, box_h=0.46, gap=0.075, color=CYAN, tsize=11.5, dsize=10):
    for i, (t, d) in enumerate(steps):
        cy = y + Inches(i * (box_h + gap))
        d_ = Inches(0.4)
        add_box(slide, x, cy + (Inches(box_h) - d_) / 2, d_, d_, fill=color, shape=MSO_SHAPE.OVAL)
        tf = txbox(slide, x, cy + (Inches(box_h) - d_) / 2, d_, d_, anchor=MSO_ANCHOR.MIDDLE)
        p = para(tf, True); p.alignment = PP_ALIGN.CENTER
        _run(p, str(i + 1), size=12.5, bold=True, color=DARKTXT)
        tf = txbox(slide, x + Inches(0.52), cy, w - Inches(0.52), Inches(box_h), anchor=MSO_ANCHOR.MIDDLE)
        p = para(tf, True)
        _run(p, t, size=tsize, bold=True, color=WHITE)
        if d:
            _run(p, "   " + d, size=dsize, color=MUTED)

def real_case_slide(kicker, title, tagline_text, color, problem, flow, actions, source, note):
    s = new_slide()
    header(s, kicker, title, color=color, title_size=24)
    tagline(s, tagline_text, color=color)
    add_box(s, Inches(0.62), Inches(2.02), Inches(5.95), Inches(4.72), fill=PANEL, line=BORDER_D,
            shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=0.75)
    tf = txbox(s, Inches(0.9), Inches(2.18), Inches(5.4), Inches(0.3))
    p = para(tf, True); _run(p, "发生了什么", size=13, bold=True, color=color)
    for item in problem:
        p = para(tf); p.space_before = Pt(10); p.line_spacing = 1.15
        _run(p, "▸ " + item, size=12.2, color=TEXT)
    add_box(s, Inches(0.9), Inches(4.28), Inches(5.35), Inches(1.8), fill=(CYAN_P if color != ORANGE else AMBER_P),
            line=color, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
    tf = txbox(s, Inches(1.1), Inches(4.46), Inches(4.95), Inches(1.42), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); p.alignment = PP_ALIGN.CENTER
    _run(p, flow[0], size=13, bold=True, color=WHITE)
    p = para(tf); p.alignment = PP_ALIGN.CENTER; p.space_before = Pt(9)
    _run(p, flow[1], size=11.5, color=color)
    add_box(s, Inches(6.9), Inches(2.02), Inches(5.8), Inches(4.72), fill=GREEN_P, line=GREEN,
            shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
    tf = txbox(s, Inches(7.18), Inches(2.18), Inches(5.25), Inches(0.3))
    p = para(tf, True); _run(p, "项目怎么做  ·  可复用做法", size=13, bold=True, color=GREEN)
    for item in actions:
        p = para(tf); p.space_before = Pt(9); p.line_spacing = 1.1
        _run(p, "▸ " + item, size=11.4, color=TEXT)
    tf = txbox(s, Inches(0.86), Inches(6.85), Inches(11.8), Inches(0.18))
    p = para(tf, True); _run(p, "来源：" + source, size=8.5, color=DIM, name=FONT_M)
    footer(s, "Use·案例")
    notes(s, note)

def table(slide, x, y, w, col_ratios, rows, header_fill=PURPLE, row_h=0.34, header_h=0.36,
          fsize=11, header_fsize=11):
    ncols = len(col_ratios)
    nrows = len(rows)
    total = sum(col_ratios)
    widths = [Emu(int(w * (cr / total))) for cr in col_ratios]
    gt = slide.shapes.add_table(nrows, ncols, x, y, w, Emu(int(row_h * nrows + (header_h - row_h)))).table
    for i, cw in enumerate(widths):
        gt.columns[i].width = cw
    gt.rows[0].height = Inches(header_h)
    for ri in range(1, nrows):
        gt.rows[ri].height = Inches(row_h)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = gt.cell(ri, ci)
            cell.margin_left = Inches(0.08); cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.02); cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill if ri == 0 else (ROW1 if ri % 2 == 1 else ROW2)
            tf = cell.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]
            if ri == 0:
                _run(p, val, size=header_fsize, bold=True, color=DARKTXT)
            else:
                _run(p, val, size=fsize, color=TEXT)
    return gt

# ================================================================ SLIDES

# ---------------- 1 cover ----------------
s = new_slide()
top = add_box(s, Inches(0.02), Inches(0.02), prs.slide_width - Inches(0.04), Inches(0.05), fill=CYAN); _alpha(top, 55)
for i, (w_, a) in enumerate([(2.5, 28), (1.7, 16), (1.0, 9)]):
    ln = add_box(s, Inches(1.0), Inches(1.02 + 0.14 * i), Inches(w_), Inches(0.045), fill=CYAN)
    _alpha(ln, a)
add_box(s, Inches(10.72), Inches(1.35), Inches(0.48), Inches(3.0), fill=CYAN, shape=MSO_SHAPE.PARALLELOGRAM, adj=0.2)
add_box(s, Inches(11.92), Inches(2.95), Inches(0.28), Inches(1.45), fill=PURPLE, shape=MSO_SHAPE.PARALLELOGRAM, adj=0.2)
tf = txbox(s, Inches(1.0), Inches(1.52), Inches(9.2), Inches(0.5))
p = para(tf, True); _run(p, "HARNESS ENGINEERING KIT  ·  AEGIS AGENT 实战样本", size=13, bold=True, color=CYAN)
tf = txbox(s, Inches(1.0), Inches(1.98), Inches(9.4), Inches(1.85))
p = para(tf, True); _run(p, "把 AI Agent，变成", size=42, bold=True, color=WHITE)
p = para(tf); p.space_before = Pt(4)
_run(p, "可控、可批、可验、可审计的工程", size=42, bold=True, color=CYAN)
p = para(tf); p.space_before = Pt(8)
_run(p, "以 aegis Agent 为例 · 从模型调用到仓库规则，走通一次真实工程闭环", size=16, bold=True, color=CYAN)
add_box(s, Inches(1.0), Inches(4.9), Inches(10.2), Inches(0.6), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14)
tf = txbox(s, Inches(1.24), Inches(4.9), Inches(9.8), Inches(0.6), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True)
_run(p, "今天不讲抽象架构，围绕 aegis Agent 走一遍：怎么接入、怎么改动、怎么把失败变成护栏", size=13, bold=True, color=WHITE)
p = para(tf); _run(p, "  （开箱即用，细节在仓库里）", size=11, color=MUTED)
chips(s, Inches(1.0), Inches(6.08), 0, ["v0.5.1", "MIT · OpenSpec", "多 Agent 适配", "上下文中英双语"],
      fill=BG2, color=CYAN, size=12, line=CYAN)
add_box(s, Inches(0.02), Inches(7.16), prs.slide_width - Inches(0.04), Inches(0.30), fill=BG2)
tf = txbox(s, Inches(1.0), Inches(6.66), Inches(11.6), Inches(0.4))
p = para(tf, True); _run(p, "分享人：沈学海   ·   ", size=11, bold=True, color=WHITE)
_run(p, "github.com/8425334/harness-engineering-kit   ·   技术团队内部知识分享", size=11, color=DIM)
notes(s, "开场重新定位：本场不穷尽方法论，聚焦三件事——①看清框架结构；②解释 aegis 实际用到的概念；③形成可执行的使用路径。细节留在仓库。")

# ---------------- 2 agenda ----------------
s = new_slide()
header(s, "AGENDA", "五段结构：框架 → aegis 实现 → 可执行落地", color=GREEN)
parts = [
    ("01  Why", "为什么 AI 能写码，却不能可靠交付", "三缺失；LLM 智能 vs 工程确定性的分工", GREEN),
    ("02  What", "先看一张框架图", "HEK 五件事，一件事一页，不用每件都展开", CYAN),
    ("03  How", "只讲三条底层原则", "规格先行 · 上下文按需 · 门禁留证据", PURPLE),
    ("04  Grow", "错误怎么反哺成门禁", "Self-Refine · 经验记忆 · Fitness，合并成一页讲", PINK),
    ("05  Use", "重点：落地使用", "怎么接入 · 一次改动怎么走 · 文件速查 · aegis 实例", ORANGE),
]
y = Inches(1.72)
for tag, t, d, c in parts:
    add_box(s, Inches(0.9), y, Inches(11.5), Inches(0.92), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14)
    add_box(s, Inches(0.9), y, Inches(0.13), Inches(0.92), fill=c)
    tf = txbox(s, Inches(1.22), y + Inches(0.10), Inches(2.1), Inches(0.6), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); _run(p, tag, size=16, bold=True, color=c)
    tf = txbox(s, Inches(3.45), y + Inches(0.08), Inches(5.45), Inches(0.75), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); _run(p, t, size=14.5, bold=True, color=WHITE)
    tf = txbox(s, Inches(9.0), y + Inches(0.10), Inches(3.35), Inches(0.75), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); p.alignment = PP_ALIGN.RIGHT
    _run(p, d, size=9.5, color=MUTED)
    y += Inches(0.92) + Inches(0.13)
add_box(s, Inches(0.9), Inches(6.62), Inches(11.5), Inches(0.42), fill=PANEL2, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14, line_w=1.0)
tf = txbox(s, Inches(1.12), Inches(6.62), Inches(11.1), Inches(0.42), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True)
_run(p, "▍ 本场主线：", size=11, bold=True, color=GREEN)
_run(p, "把 HEK 当『给 AI 装刹车和方向盘』——大多数人需要的不是全部细节，而是知道框架在哪、怎么用起来。", size=11.5, bold=True, color=WHITE)
footer(s, "Agenda")
notes(s, "五段导览，重心后移：What 用一张框架图立骨架，How 只讲 aegis 实际用到的概念，Grow 合并成一页，重点落在 Use 的可执行路径。")

# ---------------- 3 pain ----------------
s = new_slide()
header(s, "WHY", "问题：让 AI 写代码很容易，让它“可靠交付”很难", color=GREEN)
tagline(s, "核心判断：无需先学完整套理论；先让 AI 读规则，再按 change 执行。", color=GREEN, y=1.5, h=0.42)
cards = [
    ("上下文缺失", "AI 不知道模块边界 / 依赖方向 / 允许的命令", CYAN, "只能靠临时搜索“猜”"),
    ("契约缺失", "需求直接进实现，边写边改，职责漂移", PURPLE, "没有规格对对齐，测试无从写起"),
    ("验证缺失", "“编译通过”≠“行为正确”", RED, "没有门禁与证据，生成了=做完了"),
]
x = Inches(0.9)
for title, d1, c, d2 in cards:
    add_box(s, x, Inches(2.1), Inches(3.66), Inches(2.1), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.08)
    add_box(s, x, Inches(2.1), Inches(3.66), Inches(0.6), fill=c, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.9)
    tf = txbox(s, x + Inches(0.24), Inches(2.2), Inches(3.2), Inches(0.5))
    p = para(tf, True); _run(p, title, size=15, bold=True, color=DARKTXT)
    tf = txbox(s, x + Inches(0.24), Inches(2.95), Inches(3.2), Inches(1.1))
    p = para(tf, True); _run(p, d1, size=12, color=TEXT)
    p = para(tf); p.space_before = Pt(6); _run(p, "→ " + d2, size=11.5, bold=True, color=c)
    x += Inches(3.66) + Inches(0.26)
add_box(s, Inches(0.9), Inches(4.8), Inches(11.5), Inches(1.4), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.08, line_w=1.0)
tf = txbox(s, Inches(1.15), Inches(4.95), Inches(11.0), Inches(1.15))
p = para(tf, True); _run(p, "aegis 的工程回答：", size=12.5, bold=True, color=GREEN)
p = para(tf); p.space_before = Pt(5); p.line_spacing = 1.2
_run(p, "「LLM 负责理解，仓库负责约束。」先把边界、规格和完成标准放进仓库，", size=12, color=TEXT)
_run(p, "再让 Agent 按步骤执行并留下证据。", size=12, bold=True, color=WHITE)
footer(s, "Why")
notes(s, "Why 只做定位：不是讲模型原理，而是告诉听众为什么项目里要多几份文件和几道门。")

# ---------------- 4 division ----------------
s = new_slide()
header(s, "WHY", "核心分工：AI 负责生成，人和仓库负责放行", color=GREEN)
table(s, Inches(0.9), Inches(1.72), Inches(11.55), [1.1, 1.6, 1.9],
      [
          ["", "AI 可以做", "项目必须管"],
          ["理解", "读需求、提方案、写草稿", "边界、职责、依赖方向"],
          ["执行", "按任务生成实现", "审批、门禁、回滚条件"],
          ["完成", "给出“应该可以”", "测试、证据、归档结果"],
      ], header_fill=CYAN, row_h=0.5)
add_box(s, Inches(0.9), Inches(4.85), Inches(11.5), Inches(1.15), fill=PANEL2, line=CYAN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.09, line_w=1.0)
tf = txbox(s, Inches(1.15), Inches(4.95), Inches(11.0), Inches(0.95))
p = para(tf, True)
_run(p, "一句判断：", size=13, bold=True, color=CYAN)
_run(p, "LLM 回答“它能做”，Harness 决定“允许它怎么做、做完怎么证明”。", size=13.5, bold=True, color=WHITE)
p = para(tf); p.space_before = Pt(4)
_run(p, "所以 HEK 的用法很简单：让 AI 先读 → 先批 → 再做 → 做完留证据。", size=11.5, color=MUTED)
footer(s, "Why")
notes(s, "把分工讲成一条天然分割线，收敛到一句可带走的话。不做细节展开，只建立『模型自述 vs 外部证明』的心智模型。")

# ---------------- 5 framework overview ----------------
s = new_slide()
header(s, "WHAT · 框架总览", "HEK = Harness Engineering Kit，一次受控变更 → 五件事：想法→可靠代码", color=CYAN)
tagline(s, "关键规则：原则管住智能 · 流程管住节奏 · 产物管住对账 · 治理管住放行 · 反哺管住长进", color=CYAN)
frame_rows = [
    ("① 原则", "LLM 只做理解，确定的部分交给管线", "根 CLAUDE.md · agent-policy.yaml · AI.md", CYAN),
    ("② 流程", "一条受控生命周期：探 → 提 → 做 → 验 → 并 → 存", "openspec/changes/* 生命周期", GREEN),
    ("③ 产物", "proposal / spec / design / tasks 四件套 + 权威规格", "openspec/changes/ · openspec/specs/", PURPLE),
    ("④ 治理", "审批绑定 + 门禁 + 证据，放行才写码", "docs/fitness/ · execution-evidence", ORANGE),
    ("⑤ 反哺", "失败先记录，重复问题再固化为规则", "docs/fitness/ · docs/methodology/lessons/", PINK),
]
y = Inches(2.02)
rh, rg = 0.78, 0.09
for name, what, where, c in frame_rows:
    add_box(s, Inches(0.62), y, Inches(2.0), Inches(rh), fill=c, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.12)
    tf = txbox(s, Inches(0.62), y, Inches(2.0), Inches(rh), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); p.alignment = PP_ALIGN.CENTER
    _run(p, name, size=15, bold=True, color=DARKTXT); p.alignment = PP_ALIGN.CENTER
    tf = txbox(s, Inches(2.8), y, Inches(6.1), Inches(rh), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); p.line_spacing = 1.0
    _run(p, what, size=12, bold=True, color=WHITE)
    tf = txbox(s, Inches(9.05), y, Inches(3.9), Inches(rh), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); p.alignment = PP_ALIGN.RIGHT
    _run(p, where, size=10, color=c, name=FONT_M)
    y += Inches(rh + rg)
add_box(s, Inches(0.62), Inches(6.5), Inches(12.1), Inches(0.52), fill=PANEL2, line=CYAN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14, line_w=1.0)
tf = txbox(s, Inches(0.86), Inches(6.5), Inches(11.7), Inches(0.52), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True)
_run(p, "接下来 How 只解释 aegis 实际用到的概念，Use 给出五件事的落地路径。", size=12, bold=True, color=CYAN)
footer(s, "What")
notes(s, "这张是全场的骨架。五件事各占一行，不展开，先让听众建立整体地图：原则/流程/产物/治理/反哺各落在仓库哪些路径。后面所有页都回指这五个框。")

# ---------------- 6 harness concept ----------------
s = new_slide()
header(s, "WHAT · Harness 是什么", "HEK 是项目里的 AI 使用说明书", color=CYAN)
tagline(s, "三层分工：Prompt 说清问题，Context 带对文件，Harness 管住变更。", color=CYAN)
ILLUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "harness-metaphor-bw.jpg")
pic_card(s, ILLUS, Inches(0.35), Inches(2.0), Inches(4.4), Inches(4.7))
tf = txbox(s, Inches(5.1), Inches(2.0), Inches(7.5), Inches(4.8))
for title, tx in [
    ("Prompt Engineering", "把问题说清：这次要解决什么。"),
    ("↓  Context Engineering", "把文件带对：只加载命中的模块规则。"),
    ("↓  Harness Engineering", "把变更管住：规格、审批、任务、验证和证据都放回仓库。"),
]:
    p = para(tf, True); p.space_after = Pt(7)
    _run(p, "▍ ", size=12, bold=True, color=CYAN)
    _run(p, title, size=14, bold=True, color=WHITE)
    p = para(tf); p.line_spacing = 1.2
    _run(p, tx, size=11.5, color=MUTED)
footer(s, "What")
notes(s, "用缰绳隐喻 + 三级演进：Prompt → Context → Harness。两张缰绳（Agent 级+Project 级）中，本次只展开 Project Harness。配图为黑白线稿（harness-metaphor-bw.jpg）。")

# ---------------- 7 openspec concept+case ----------------
s = new_slide()
header(s, "HOW · 规格驱动 OpenSpec", "先写规格，再写代码：需求 → 规格 → 实现", color=PURPLE)
tagline(s, "关键规则：一个 change＝四件套（proposal/spec/design/tasks），起点是规格，不是代码。", color=PURPLE)
add_box(s, Inches(0.62), Inches(1.98), Inches(6.1), Inches(4.55), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.04, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(2.1), Inches(5.7), Inches(0.3))
p = para(tf, True); _run(p, "四件套各自干什么", size=11, bold=True, color=PURPLE)
four = [
    ("proposal.md", "一句话立界：为什么做、范围与影响"),
    ("spec.md（能力）", "WHEN/THEN 描述可观测行为，先对齐‘要什么’"),
    ("design.md", "给开发者确认的方案包：架构·职责·时序·接口·风险"),
    ("tasks.md", "唯一任务源，勾选必须对应一次成功执行 + 证据"),
]
tf = txbox(s, Inches(0.86), Inches(2.48), Inches(5.7), Inches(3.9))
first = True
for t, d in four:
    p = para(tf, first); first = False
    p.space_after = Pt(6); p.line_spacing = 1.1
    _run(p, "▸ " + t, size=11, bold=True, color=CYAN, name=FONT_M)
    _run(p, "  " + d, size=10.5, color=TEXT)
add_box(s, Inches(0.62), Inches(6.6), Inches(6.1), Inches(0.5), fill=CYAN_P, line=CYAN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14, line_w=1.0)
tf = txbox(s, Inches(0.84), Inches(6.6), Inches(5.7), Inches(0.5), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); _run(p, "规格即权威：代码实现规格、验证对照规格", size=10.5, bold=True, color=CYAN)
add_box(s, Inches(6.98), Inches(1.98), Inches(6.0), Inches(5.12), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.05, line_w=1.0)
tf = txbox(s, Inches(7.2), Inches(2.1), Inches(5.6), Inches(0.3))
p = para(tf, True); _run(p, "aegis 真实 change：capability-driven-ai-platform", size=10.5, bold=True, color=GREEN)
tree = [
    "openspec/changes/",
    "  └ archive/2026-09-02-capability-driven-ai-platform/",
    "      ├ proposal.md              为什么要做",
    "      ├ specs/capability-planner/spec.md      WHEN/THEN",
    "      ├ specs/capability-metadata/spec.md     能力元数据",
    "      ├ specs/capability-routing/spec.md      路由",
    "      ├ design.md                6 模块技术方案",
    "      └ tasks.md                 任务分解与勾选",
]
tf = txbox(s, Inches(7.2), Inches(2.48), Inches(5.6), Inches(3.6))
first = True
for ln in tree:
    p = para(tf, first); first = False
    p.space_after = Pt(2.4); p.line_spacing = 1.0
    c = MUTED if ln.startswith("  └") else (GREEN if "spec.md" in ln else TEXT)
    _run(p, ln, size=8.6, color=c, name=FONT_M)
add_box(s, Inches(6.98), Inches(6.4), Inches(6.0), Inches(0.7), fill=GREEN, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14)
tf = txbox(s, Inches(7.2), Inches(6.4), Inches(5.6), Inches(0.7), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); p.line_spacing = 1.05
_run(p, "同一次变更：规格分多份、设计一件、任务一件——四件各司其职。", size=10, bold=True, color=DARKTXT)
footer(s, "How · OpenSpec")
notes(s, "保留一页 OpenSpec 概念即可；重点让听众知道真实 change 在哪里、四类产物分别去哪看。")

# ---------------- 8 lifecycle ----------------
s = new_slide()
header(s, "HOW · 受控变更生命周期", "一次变更走一条主线，OpenSpec 是所有者，HEK 是治理外壳", color=PURPLE)
labels = ["Explore", "Propose", "Apply", "Verify", "Sync", "Archive"]
lcolors = [GREEN, CYAN, PURPLE, PINK, ORANGE, RED]
x = Inches(0.62)
for i, l in enumerate(labels):
    add_box(s, x, Inches(1.62), Inches(1.98), Inches(0.62), fill=lcolors[i], shape=MSO_SHAPE.CHEVRON, adj=0.30)
    tf = txbox(s, x + Inches(0.18), Inches(1.67), Inches(1.62), Inches(0.5), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); _run(p, l, size=12.5, bold=True, color=DARKTXT)
    x += Inches(2.05)
desc = [
    ("Explore 探", "读上下文 · RAM/D 先想清 · 提议 change", CYAN),
    ("Propose 提", "写 proposal + spec + design，交给人批", GREEN),
    ("Apply 做", "按 tasks.md 逐任务实现，边做边留证据", PURPLE),
    ("Verify 验", "对照规格跑校验 / Fitness 门禁", PINK),
    ("Sync 并", "delta 验证通过 → 合回权威规格库", ORANGE),
    ("Archive 存", "变更归档，结论沉淀为规则", RED),
]
y = Inches(2.6)
for t, d, c in desc:
    add_box(s, Inches(0.62), y, Inches(0.14), Inches(0.62), fill=c)
    tf = txbox(s, Inches(0.95), y, Inches(12.0), Inches(0.62), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True)
    _run(p, t + "   ", size=13, bold=True, color=c)
    _run(p, d, size=12, color=TEXT)
    y += Inches(0.62) + Inches(0.10)
add_box(s, Inches(0.62), Inches(6.5), Inches(12.1), Inches(0.56), fill=PANEL2, line=PURPLE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14, line_w=1.0)
tf = txbox(s, Inches(0.86), Inches(6.5), Inches(11.7), Inches(0.56), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True)
_run(p, "操作骨架：", size=12, bold=True, color=PURPLE)
_run(p, "这六步是“一次受控变更”的模板；aegis 每条 change 都沿此路径执行：『探→提→做→验→并→存』。", size=12, bold=True, color=WHITE)
footer(s, "How · 生命周期")
notes(s, "生命周期压成一页：顶部六步 chevron，下面每步一句话 + 主色。不展开每步细节，只给出模板心智。")

# ---------------- 9 context ----------------
s = new_slide()
header(s, "HOW · 确定性上下文", "改代码前，先让 AI 知道自己“站在哪”", color=PURPLE)
tagline(s, "关键规则：上下文不靠全塞，而靠『机器索引 + 路径级精读』——只加载命中的那层。", color=PURPLE)
add_box(s, Inches(0.62), Inches(1.98), Inches(5.5), Inches(4.5), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.05, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(2.1), Inches(5.0), Inches(0.3))
p = para(tf, True); _run(p, "怎么落地：路径级上下文（aegis 8 模块）", size=10.5, bold=True, color=PURPLE)
mods = ["根 ai.json（≤4096B）先做路径路由", "根 AI.md（全仓规则）", "aegis-core / AI.md（内核纯契约）", "aegis-runtime / AI.md（运行时）", "aegis-ai-spring / AI.md（模型适配）", "aegis-agent / AI.md（supervisor·log）", "aegis-channel / AI.md（渠道）", "aegis-application / AI.md（入口）"]
tf = txbox(s, Inches(0.86), Inches(2.5), Inches(5.1), Inches(3.9))
first = True
for m in mods:
    p = para(tf, first); first = False
    p.space_after = Pt(5); p.line_spacing = 1.08
    _run(p, "▸ ", size=10, bold=True, color=PURPLE)
    _run(p, m, size=10.3, color=TEXT, name=FONT_M)
add_box(s, Inches(0.62), Inches(6.5), Inches(5.5), Inches(0.56), fill=AMBER_P, line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14, line_w=1.0)
tf = txbox(s, Inches(0.84), Inches(6.5), Inches(5.1), Inches(0.56), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); _run(p, "Fail-closed：缺任一层 → 拒绝开工", size=10.5, bold=True, color=ORANGE)
add_box(s, Inches(6.4), Inches(1.98), Inches(6.3), Inches(5.08), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.07, line_w=1.0)
tf = txbox(s, Inches(6.62), Inches(2.1), Inches(5.9), Inches(0.3))
p = para(tf, True); _run(p, "每份 AI.md 主要回答五类问题（aegis-core 实样）", size=11, bold=True, color=GREEN)
ai = [
    ("Scope", "governs aegis-core —— 平台内核（纯 Java 契约）"),
    ("Responsibilities", "core/agent 契约 · core/routing 端口 · 单测"),
    ("Boundaries", "禁止 Spring/web/数据；只依赖 JDK"),
    ("Verification", "./mvnw -pl aegis-core test"),
    ("Navigation", "入口点 · 关联契约 · Owner"),
]
tf = txbox(s, Inches(6.62), Inches(2.5), Inches(5.9), Inches(3.6))
first = True
for k, v in ai:
    p = para(tf, first); first = False
    p.space_after = Pt(6); p.line_spacing = 1.05
    _run(p, k, size=10.5, bold=True, color=GREEN, name=FONT_M)
    _run(p, "  " + v, size=10.5, color=TEXT)
footer(s, "How · 上下文")
notes(s, "上下文落地到 aegis：根 ai.json 做机器路由，实际加载根 AI.md、命中的模块 AI.md，以及 docs/fitness 等受保护规则。重点是路径命中，不是把所有文件塞进 prompt。")

# ---------------- 10 delta specs ----------------
s = new_slide()
header(s, "HOW · 规格演进 Delta Specs", "权威库只被走完生命周期的变更更新", color=PURPLE)
tagline(s, "关键规则：权威 specs 永远描述『当前系统』；进行中的想法只活在 change 的增量里，合回才算数。", color=PURPLE)
add_box(s, Inches(0.62), Inches(1.98), Inches(6.0), Inches(4.55), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.04, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(2.1), Inches(5.6), Inches(0.3))
p = para(tf, True); _run(p, "openspec/specs/ · 权威库（真实节选）", size=10.5, bold=True, color=PURPLE)
specs = [
    "feishu-card-streaming / feishu-channel / website-channel",
    "feishu-streaming-interaction / session-management",
    "agent-runtime / agent-routing / multi-agent",
    "capability-planner / capability-metadata / capability-routing",
    "capability-observability / log-analysis / log-analysis-closed-loop",
    "cls-log-fetch / model-context-window / log-payload-boundary",
    "model-provider / model-rate-limit / model-context-window",
    "skill-declarative-loading / skill-runtime / tool-runtime",
    "intent-classification / code-location / task-orchestration",
    "",
    "每一份都对应一次走完生命周期的变更，没有半截规格。",
]
tf = txbox(s, Inches(0.86), Inches(2.5), Inches(5.6), Inches(3.9))
first = True
for ln in specs:
    p = para(tf, first); first = False
    p.space_after = Pt(2.4); p.line_spacing = 1.0
    _run(p, ln, size=8.7, color=MUTED if (ln.startswith("每") or ln == "") else TEXT, name=FONT_M)
add_box(s, Inches(6.9), Inches(1.98), Inches(5.8), Inches(4.55), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.07, line_w=1.0)
tf = txbox(s, Inches(7.12), Inches(2.1), Inches(5.4), Inches(0.3))
p = para(tf, True); _run(p, "权威库怎么‘长’出来（change → 合回）", size=11, bold=True, color=GREEN)
maps = [
    ("log-analysis-closed-loop", "→ log-analysis-closed-loop / spec.md", "闭环从草案变权威"),
    ("capability-driven-ai-platform", "→ capability-* ×4 / spec.md", "一次变更长出一组"),
    ("intent-classification-model", "→ intent-classification / spec.md", "分类规则进入权威规格"),
    ("website-channel", "→ website-channel / spec.md", "新渠道接入即入权威"),
]
tf = txbox(s, Inches(7.12), Inches(2.5), Inches(5.4), Inches(3.9))
first = True
for ch, sp, note in maps:
    p = para(tf, first); first = False
    p.space_after = Pt(2.5); p.line_spacing = 1.06
    _run(p, ch, size=9.5, bold=True, color=CYAN, name=FONT_M)
    p = para(tf); p.line_spacing = 1.0
    _run(p, "   " + sp, size=9, color=GREEN, name=FONT_M)
    p = para(tf); p.space_after = Pt(9); p.line_spacing = 1.0
    _run(p, "   " + note, size=9, color=MUTED)
footer(s, "How · 规格演进")
notes(s, "规格演进：左权威库 30+ 份，右四条『变更→权威规格』真实增长线。仓库永不描述进行中想法；Verify→Sync 通过才合回。")

# ---------------- 11 governance ----------------
s = new_slide()
header(s, "HOW · 治理与门禁", "放行前要人批，批完才授权写码，完成 = 门禁 + 证据", color=PURPLE)
tagline(s, "关键规则：design.md 是给人确认的方案包——架构·职责·时序·接口·波次·风险，批前一行实现都不写。", color=PURPLE)
add_box(s, Inches(0.62), Inches(1.98), Inches(6.0), Inches(2.5), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(2.1), Inches(5.6), Inches(0.3))
p = para(tf, True); _run(p, "Design 门禁三步", size=11, bold=True, color=PURPLE)
for t in ["① 结构校验：proposal/spec/design/tasks 齐备、schema 合法",
          "② 开发者确认：把方案 + 边界 + 波次 + 风险呈现出来请求确认",
          "③ 审批绑定：外部审批记录 + 契约摘要 → Apply 才被授权"]:
    p = para(tf); p.space_before = Pt(7); p.line_spacing = 1.15
    _run(p, t, size=11.5, color=TEXT)
add_box(s, Inches(0.62), Inches(4.66), Inches(6.0), Inches(2.2), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.07, line_w=1.0)
tf = txbox(s, Inches(0.86), Inches(4.78), Inches(5.6), Inches(2.0))
p = para(tf, True); _run(p, "Apply 与证据", size=11, bold=True, color=GREEN)
for t in ["tasks.md 是唯一任务源，勾选必须对应一次成功执行",
          "证据写回 execution-evidence.json，全文可审计",
          "『代码生成了』≠『做完了』——门禁通过才算"]:
    p = para(tf); p.space_before = Pt(6.5); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=11, color=TEXT)
add_box(s, Inches(6.9), Inches(1.98), Inches(5.8), Inches(4.88), fill=AMBER_P, line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
tf = txbox(s, Inches(7.12), Inches(2.1), Inches(5.4), Inches(0.3))
p = para(tf, True); _run(p, "如果跳过门禁直接写码", size=11, bold=True, color=ORANGE)
for t in ["能力写哪、边界交给谁——边写边拍脑袋",
          "Spec/Design 一变，原审批悄悄失效无人知",
          "『批过=永远有效』：架构漂移没被拦，越走越失控",
          "多模块并行没有统一契约，各写各的不正交",
          "没有波次与回滚，出问题只能整体回退"]:
    p = para(tf); p.space_before = Pt(6); p.line_spacing = 1.12
    _run(p, "✕ " + t, size=11, color=TEXT)
footer(s, "How · 治理")
notes(s, "把『Design 门禁 + Apply 证据』合并成一页，右边用反面对照讲清跳过门禁的代价。aegis 的 capability 平台里就是这么走的。")

# ---------------- 12 ramd ----------------
s = new_slide()
header(s, "HOW · 先想清再写 RAM/D", "AI 写码最大的风险：代码能跑，但悄悄打破系统边界", color=PURPLE)
tagline(s, "关键规则：RAM/D 就是四步——Read 读懂边界，Analyze 想清依赖，Model/Decompose 先出契约，再放行写实现。", color=PURPLE)
num_steps_v(s, Inches(0.9), Inches(2.0), Inches(6.2), [
    ("Read 读", "读上下文/边界/依赖方向，先知道站在哪"),
    ("Analyze 析", "把需求拆成职责，想清数据与调用关系"),
    ("Model 建模（后端）", "产出接口契约/抽象，审批后才放行实现"),
    ("Decompose 分解（前端）", "产出类型与组件结构，再放行实现"),
], box_h=0.72, gap=0.14, color=CYAN, tsize=13, dsize=11)
add_box(s, Inches(7.35), Inches(2.0), Inches(5.35), Inches(4.6), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=0.75)
tf = txbox(s, Inches(7.6), Inches(2.15), Inches(4.9), Inches(0.3))
p = para(tf, True); _run(p, "对照：直接生成 vs RAM/D 先想清", size=11.5, bold=True, color=CYAN)
for t, ok in [
    ("直接生成：边写边拍脑袋，边界值何时算", True),
    ("先 RAM/D：契约先行，风险在写码前就暴露", False),
]:
    p = para(tf); p.space_before = Pt(9); p.line_spacing = 1.2
    _run(p, ("✔ " if not ok else "✕ ") + t, size=12, bold=True, color=(GREEN if not ok else RED))
add_box(s, Inches(7.35), Inches(6.4), Inches(5.35), Inches(0.66), fill=PANEL2, line=CYAN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14, line_w=1.0)
tf = txbox(s, Inches(7.58), Inches(6.4), Inches(5.0), Inches(0.66), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); p.line_spacing = 1.05
_run(p, "RAM/D 可视为每次动手前 2 分钟的心智检查，无需扩展成流程文档。", size=10, bold=True, color=CYAN)
footer(s, "How · RAM/D")
notes(s, "RAM/D 精简成一页：四步 + 反面对照。强调它就是个心智检查，不用上纲上线。不再展开 LLM 抽象/后端前端两个 Profile。可为现场演示简单走一个控制器例子。")

# ---------------- 13 grow ----------------
s = new_slide()
header(s, "GROW · 反哺成门禁与经验", "错误不是一次性的，要变成下一次的规则", color=PINK)
tagline(s, "关键规则：反哺是一条闭环——Self-Refine 先自查，经验记忆累积『反复失败』，Fitness 把教训固化成硬门禁。", color=PINK)
add_box(s, Inches(0.62), Inches(1.98), Inches(6.0), Inches(2.2), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(2.1), Inches(5.6), Inches(0.3))
p = para(tf, True); _run(p, "① Self-Refine：有界的内层自检", size=11, bold=True, color=PINK)
for t in ["生成 → 模型批判 → 优化 → 再检查", "环心有界闭环（≤ max_iterations）", "每轮对照已批需求与风险标准，记录具体修改"]:
    p = para(tf); p.space_before = Pt(5.5); p.line_spacing = 1.12
    _run(p, "▸ " + t, size=10.6, color=TEXT)
add_box(s, Inches(0.62), Inches(4.32), Inches(6.0), Inches(2.55), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(4.44), Inches(5.6), Inches(0.3))
p = para(tf, True); _run(p, "② 经验记忆 · ③ Fitness 门禁", size=11, bold=True, color=PINK)
for t in ["经验记忆：把跨变更『反复失败』沉淀为可检索的预防",
          "Fitness：把『什么时候算做完』编码成可执行规则",
          "验证通过的经验 → 升级成 Fitness 硬门禁（docs/fitness/）"]:
    p = para(tf); p.space_before = Pt(5.5); p.line_spacing = 1.12
    _run(p, "▸ " + t, size=10.6, color=TEXT)
add_box(s, Inches(6.9), Inches(1.98), Inches(5.8), Inches(4.89), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.07, line_w=1.0)
tf = txbox(s, Inches(7.12), Inches(2.1), Inches(5.4), Inches(0.3))
p = para(tf, True); _run(p, "aegis 真实的 失败→修复→预防", size=11, bold=True, color=GREEN)
lines = [
    ("token 超预算 / 上下文超窗", "model-token-budget-gate + model-context-window", "限流排队或裁剪，保留降级路径"),
    ("日志负载太大拖垮分析", "log-payload-boundary-capping", "按规则降采样并保留关键事件"),
    ("代码查询不问人、误读", "code-query-human-confirmation", "Read 阶段人工确认成护栏"),
]
tf = txbox(s, Inches(7.12), Inches(2.5), Inches(5.4), Inches(4.3))
first = True
for fail, fix, prev in lines:
    p = para(tf, first); first = False
    p.space_after = Pt(2.5); p.line_spacing = 1.05
    _run(p, "失败事件 → ", size=10, bold=True, color=ORANGE); _run(p, fail, size=10, color=TEXT)
    p = para(tf); p.line_spacing = 1.05
    _run(p, "修复变更 → ", size=10, bold=True, color=PINK); _run(p, fix, size=10, color=TEXT, name=FONT_M)
    p = para(tf); p.space_after = Pt(10); p.line_spacing = 1.05
    _run(p, "升级预防 → ", size=10, bold=True, color=GREEN); _run(p, prev, size=10, color=TEXT)
footer(s, "Grow·反哺")
notes(s, "把 Self-Refine、经验记忆、Fitness 与运行时治理区分开：失败先形成 change 或 lesson，验证后才升级成规则；token/context/payload 主要是 aegis 的运行时规格。")

# ---------------- 14 use setup ----------------
s = new_slide()
header(s, "USE · 怎么接入", "四步把 HEK 装进项目，先跑通再加深", color=ORANGE)
tagline(s, "关键规则：接入的本质，是把上下文路由、变更流程和验收标准写成仓库契约。", color=ORANGE)
steps = [
    ("引入", "在目标仓库放好自带的地图与规则（CLAUDE.md / agent-policy.yaml / AI.md）"),
    ("初始化", "Agent 驱动地生成框架骨架：OpenSpec 区 + 治理区 + 上下文区"),
    ("定档", "选 Tier / 档位：低风险局部改动走 light，关键路径走完整门禁"),
    ("验收", "跑一次代表性变更，确认产物、门禁与证据链能闭合"),
]
num_steps_v(s, Inches(0.9), Inches(2.0), Inches(6.4), steps, box_h=0.8, gap=0.16, color=ORANGE, tsize=13, dsize=11)
add_box(s, Inches(7.6), Inches(2.0), Inches(5.1), Inches(4.7), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.07, line_w=0.75)
tf = txbox(s, Inches(7.85), Inches(2.15), Inches(4.7), Inches(0.3))
p = para(tf, True); _run(p, "框架生效后可观察到", size=11.5, bold=True, color=ORANGE)
for t in ["每次改代码前，AI 先读 AI.md / 边界，不再瞎猜",
          "发起变更，自动产出 proposal·spec·design·tasks",
          "放行前有人点确认，成功后留证据",
          "多余的深度可裁减：方法论是默认值，不是强制清单"]:
    p = para(tf); p.space_before = Pt(9); p.line_spacing = 1.2
    _run(p, "▸ " + t, size=11.5, color=TEXT)
add_box(s, Inches(7.6), Inches(6.4), Inches(5.1), Inches(0.66), fill=AMBER_P, line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14, line_w=1.0)
tf = txbox(s, Inches(7.84), Inches(6.4), Inches(4.7), Inches(0.66), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); p.line_spacing = 1.05
_run(p, "先跑通，再往深里加门禁——别一上来就上满配置。", size=10.5, bold=True, color=ORANGE)
footer(s, "Use·接入")
notes(s, "接入讲得实操：四步（引入/初始化/定档/验收）。强调先跑通再加门禁，档位可裁剪。")

# ---------------- 15 use walkthrough ----------------
s = new_slide()
header(s, "USE · 一次改动怎么走", "一次任务沿这条线执行，过程不易失序", color=ORANGE)
tagline(s, "核心判断：大多数改动沿同一条脊柱执行——读→立规格→批→做→验→存。", color=ORANGE)
wf = [
    ("① 接任务", "Read + RAM/D：读边界，想清方案再动", CYAN),
    ("② 开 change", "openspec/changes/<change-id>/ 起草 proposal + spec", GREEN),
    ("③ 等人批", "design 方案找人确认，批过才被授权写码", PURPLE),
    ("④ 按任务做", "tasks.md 逐条勾，每条成功执行留证据", PINK),
    ("⑤ 验证", "Fitness 门禁 + 对照规格，过了才算完成", ORANGE),
    ("⑥ 存进系统", "delta 合回权威库，变更归档反哺", RED),
]
y = Inches(2.0)
xcol = Inches(0.9)
for t, d, c in wf:
    add_box(s, xcol, y, Inches(0.12), Inches(0.6), fill=c)
    tf = txbox(s, xcol + Inches(0.32), y, Inches(3.1), Inches(0.6), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); _run(p, t, size=13, bold=True, color=c)
    tf = txbox(s, Inches(4.5), y, Inches(8.0), Inches(0.6), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); _run(p, d, size=12, color=TEXT)
    y += Inches(0.66) + Inches(0.06)
add_box(s, Inches(0.62), Inches(6.3), Inches(12.1), Inches(0.74), fill=PANEL2, line=CYAN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.12, line_w=1.0)
tf = txbox(s, Inches(0.9), Inches(6.3), Inches(11.6), Inches(0.74), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); p.line_spacing = 1.1
_run(p, "变更骨架：", size=12, bold=True, color=CYAN)
_run(p, "读 → 立规格 → 批 → 做 → 验 → 存。", size=13, bold=True, color=WHITE)
_run(p, "  需要人工判断的是 ①②③⑤，④⑥ 由 Agent 按规则执行。", size=11.5, color=MUTED)
footer(s, "Use·走查")
notes(s, "这是全场最实用的一页：把一次改动缩成六步脊柱，并点明哪些动脑、哪些可交给 Agent。可现场拿一个小需求从头走一遍。")

# ---------------- 16 use cheat ----------------
s = new_slide()
header(s, "USE · 需要时去哪儿", "一份速查：按任务类型定位文件", color=ORANGE)
cheat = [
    ("给 AI 带上下文 / 边界", "CLAUDE.md · AGENTS.md · AI.md · agent-policy.yaml", CYAN),
    ("发起一次变更", "openspec / changes / <change-id> /", GREEN),
    ("看方案 / 审设计", "← / design.md", PURPLE),
    ("看进度 / 勾任务", "← / tasks.md（唯一任务源）", PINK),
    ("设定完成的标准", "docs / fitness / **", ORANGE),
    ("沉淀经验 / 反哺", "变更归档 Archive · docs / methodology / lessons", RED),
]
y = Inches(1.9)
for what, where, c in cheat:
    add_box(s, Inches(0.9), y, Inches(0.12), Inches(0.62), fill=c)
    tf = txbox(s, Inches(1.25), y, Inches(5.0), Inches(0.62), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); _run(p, what, size=13, bold=True, color=WHITE)
    tf = txbox(s, Inches(6.4), y, Inches(5.7), Inches(0.62), anchor=MSO_ANCHOR.MIDDLE)
    p = para(tf, True); p.alignment = PP_ALIGN.RIGHT
    _run(p, where, size=11.5, color=c, name=FONT_M)
    y += Inches(0.62) + Inches(0.10)
add_box(s, Inches(0.62), Inches(6.55), Inches(12.1), Inches(0.5), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14, line_w=1.0)
tf = txbox(s, Inches(0.86), Inches(6.55), Inches(11.7), Inches(0.5), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True)
_run(p, "通用规则：路径即真相——看到哪一层，就只加载那一层的规则，别全塞上下文。", size=11.5, bold=True, color=GREEN)
footer(s, "Use·速查")
notes(s, "把『任务类型→文件路径』做成速查表，全部是路径级约定，无终端命令，呼应『路径即真相』。")

# ---------------- 17 use aegis ----------------
s = new_slide()
header(s, "USE · 落地成品：aegis", "照着这套结构接入：入口、运行时、适配器各守边界", color=ORANGE)
add_box(s, Inches(0.62), Inches(1.6), Inches(6.1), Inches(4.1), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.05, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(1.72), Inches(5.7), Inches(0.3))
p = para(tf, True); _run(p, "aegis 的接入地图", size=11.5, bold=True, color=ORANGE)
for t in ["aegis-application：唯一可运行入口 / 组合根", "aegis-channel：飞书等渠道，只依赖 core 契约",
          "aegis-agent：Supervisor、log-agent 与领域编排", "aegis-runtime：注册表、规划、执行、guardrail、事件",
          "aegis-core：纯 Java Agent / Tool / Skill / Gateway 契约"]:
    p = para(tf); p.space_before = Pt(6); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=11.5, color=TEXT)
add_box(s, Inches(0.62), Inches(5.9), Inches(6.1), Inches(1.0), fill=AMBER_P, line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.1, line_w=1.0)
tf = txbox(s, Inches(0.86), Inches(5.98), Inches(5.7), Inches(0.85))
p = para(tf, True); _run(p, "接入时先确认", size=11, bold=True, color=ORANGE)
p = para(tf); p.space_before = Pt(3); _run(p, "根 ai.json / AI.md 路由真实存在；模块边界与本地验证命令可执行。", size=10.5, color=MUTED)
add_box(s, Inches(6.9), Inches(1.6), Inches(5.8), Inches(4.1), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.05, line_w=1.0)
tf = txbox(s, Inches(7.12), Inches(1.72), Inches(5.4), Inches(0.3))
p = para(tf, True); _run(p, "照着做一次代表性变更", size=11.5, bold=True, color=GREEN)
for t in ["1. 从 aegis/ai.json 解析目标模块上下文", "2. 在 openspec/changes/<change-id>/ 写 proposal / spec / design / tasks",
          "3. 设计确认后 Apply；每个任务记录 execution-evidence", "4. Verify / Fitness 通过后 Sync，再 Archive",
          "5. 失败形成 lesson candidate；重复问题再升级为规则"]:
    p = para(tf); p.space_before = Pt(6); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=11.5, color=TEXT)
footer(s, "Use·aegis")
notes(s, "这页不再讲抽象收益，直接给 aegis 的模块地图和一次变更的操作顺序。")

# ---------------- 18-21 real cases ----------------
s = new_slide()
header(s, "USE · 真实案例 01", "网关只转发，决策留在 underwriter", color=CYAN, title_size=24)
tagline(s, "身份核验接入的关键不是多写一层代码，而是先划清：谁负责决策，谁只负责把契约接进来。", color=CYAN)
add_box(s, Inches(0.62), Inches(2.02), Inches(5.95), Inches(4.72), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=0.75)
tf = txbox(s, Inches(0.9), Inches(2.18), Inches(5.4), Inches(0.3))
p = para(tf, True); _run(p, "发生了什么", size=13, bold=True, color=CYAN)
for t in ["APP 需要接入用信活体核验，但 appserver 不承载风控决策。", "网关若读取路由配置、做活体判断，职责就会越界。"]:
    p = para(tf); p.space_before = Pt(10); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=12.5, color=TEXT)
add_box(s, Inches(0.9), Inches(4.2), Inches(5.35), Inches(1.85), fill=CYAN_P, line=CYAN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.05, line_w=1.0)
tf = txbox(s, Inches(1.1), Inches(4.38), Inches(4.95), Inches(1.48), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); p.alignment = PP_ALIGN.CENTER
_run(p, "APP  →  appserver  →  LoanVerifyRouteApi  →  underwriter", size=13, bold=True, color=WHITE)
p = para(tf); p.alignment = PP_ALIGN.CENTER; p.space_before = Pt(10)
_run(p, "网关：校验 / 转换 / 包装    ·    后端：路由 / 活体规则 / 结果验证", size=11.5, color=CYAN)
add_box(s, Inches(6.9), Inches(2.02), Inches(5.8), Inches(4.72), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
tf = txbox(s, Inches(7.18), Inches(2.18), Inches(5.25), Inches(0.3))
p = para(tf, True); _run(p, "项目怎么做  ·  可复用做法", size=13, bold=True, color=GREEN)
for t in ["新增 Feign Client + Request/Response DTO，Controller 保持薄层。", "underwriter 独占路由策略、活体规则下发与结果验证。", "成功、失败、Feign 异常路径都做验证；verifyId 可选透传，保持兼容。", "复用原则：新增接口先写清『谁决策、谁转发、谁留证据』。"]:
    p = para(tf); p.space_before = Pt(10); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=12, color=TEXT)
tf = txbox(s, Inches(0.86), Inches(6.85), Inches(11.8), Inches(0.18))
p = para(tf, True); _run(p, "来源：xiaohua_vn · underwriter/add-loan-liveness-verify + appserver/integrate-underwriter-identity-verification", size=8.5, color=DIM, name=FONT_M)
footer(s, "Use·案例")
notes(s, "真实案例：xiaohua_vn 的身份核验跨服务接入。讲清网关薄、后端决策、DTO 契约和错误可追踪，避免展开活体算法细节。")

# ---------------- 19 real case: sms boundary ----------------
s = new_slide()
header(s, "USE · 真实案例 02", "先拆生产者与消费者，模块边界自然清楚", color=GREEN, title_size=24)
tagline(s, "短信指标迁移没有改业务口径，先把『生成聚合事实』和『消费决策输入』拆开，复用就顺了。", color=GREEN)
add_box(s, Inches(0.62), Inches(2.02), Inches(6.05), Inches(4.72), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=0.75)
tf = txbox(s, Inches(0.9), Inches(2.18), Inches(5.5), Inches(0.3))
p = para(tf, True); _run(p, "发生了什么", size=13, bold=True, color=GREEN)
for t in ["原来 magic 同时采集短信、解释配置、计算指标、消费规则，职责过重。", "其他模块想复用短信指标，只能绕过 aggr，边界越来越模糊。"]:
    p = para(tf); p.space_before = Pt(10); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=12.5, color=TEXT)
add_box(s, Inches(0.9), Inches(4.28), Inches(2.35), Inches(1.7), fill=AMBER_P, line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
tf = txbox(s, Inches(1.08), Inches(4.47), Inches(2.0), Inches(1.25), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); p.alignment = PP_ALIGN.CENTER; _run(p, "原来", size=11, bold=True, color=ORANGE)
p = para(tf); p.alignment = PP_ALIGN.CENTER; _run(p, "magic 既生产又消费", size=12, bold=True, color=WHITE)
add_box(s, Inches(3.75), Inches(4.28), Inches(2.35), Inches(1.7), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
tf = txbox(s, Inches(3.93), Inches(4.47), Inches(2.0), Inches(1.25), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); p.alignment = PP_ALIGN.CENTER; _run(p, "现在", size=11, bold=True, color=GREEN)
p = para(tf); p.alignment = PP_ALIGN.CENTER; _run(p, "aggr 生产画像  →  magic 消费", size=11.5, bold=True, color=WHITE)
add_box(s, Inches(6.9), Inches(2.02), Inches(5.8), Inches(4.72), fill=CYAN_P, line=CYAN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
tf = txbox(s, Inches(7.18), Inches(2.18), Inches(5.25), Inches(0.3))
p = para(tf, True); _run(p, "项目怎么做  ·  可复用做法", size=13, bold=True, color=CYAN)
for t in ["aggr 承接采集 → 计算 → 结果装配，对外暴露明确 DTO。", "magic 改成 Feign 消费方，保留薄适配入口，避免一次性大拆。", "82 个指标业务口径保持不变，Map<String,Object> 换成强类型契约。", "复用原则：先问『谁生产事实，谁消费事实』，再移动代码。"]:
    p = para(tf); p.space_before = Pt(10); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=12, color=TEXT)
tf = txbox(s, Inches(0.86), Inches(6.85), Inches(11.8), Inches(0.18))
p = para(tf, True); _run(p, "来源：xiaohua_vn · openspec/changes/migrate-sms-indicator-calculation-to-aggr/", size=8.5, color=DIM, name=FONT_M)
footer(s, "Use·案例")
notes(s, "真实案例：xiaohua_vn 短信指标从 magic 迁移到 aggr。只讲职责移动、强类型契约和兼容性，不展开 82 个指标的计算细节。")

# ---------------- 20 real case: stable routing ----------------
s = new_slide()
header(s, "USE · 真实案例 03", "把随机分流改成同一用户稳定命中", color=ORANGE, title_size=24)
tagline(s, "重试场景最怕『第一次和第二次不是同一家』；把路由输入从 choose() 变成 choose(cid)，问题立刻可控。", color=ORANGE)
add_box(s, Inches(0.62), Inches(2.02), Inches(5.95), Inches(4.72), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=0.75)
tf = txbox(s, Inches(0.9), Inches(2.18), Inches(5.4), Inches(0.3))
p = para(tf, True); _run(p, "发生了什么", size=13, bold=True, color=ORANGE)
for t in ["原来 LivenessProviderRouter.choose() 随机分流，同一用户重试可能切换服务商。", "首次拿到的 livenessId 与后续服务商不匹配，排查困难，用户体验也不稳定。"]:
    p = para(tf); p.space_before = Pt(10); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=12.5, color=TEXT)
add_box(s, Inches(0.9), Inches(4.3), Inches(2.3), Inches(1.65), fill=AMBER_P, line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
tf = txbox(s, Inches(1.1), Inches(4.5), Inches(1.9), Inches(1.2), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); p.alignment = PP_ALIGN.CENTER; _run(p, "随机", size=15, bold=True, color=ORANGE)
p = para(tf); p.alignment = PP_ALIGN.CENTER; _run(p, "重试可能换服务商", size=11.5, color=TEXT)
add_box(s, Inches(3.7), Inches(4.3), Inches(2.4), Inches(1.65), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
tf = txbox(s, Inches(3.9), Inches(4.5), Inches(2.0), Inches(1.2), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); p.alignment = PP_ALIGN.CENTER; _run(p, "按 cid", size=15, bold=True, color=GREEN)
p = para(tf); p.alignment = PP_ALIGN.CENTER; _run(p, "同一用户稳定命中", size=11.5, color=TEXT)
add_box(s, Inches(6.9), Inches(2.02), Inches(5.8), Inches(4.72), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
tf = txbox(s, Inches(7.18), Inches(2.18), Inches(5.25), Inches(0.3))
p = para(tf, True); _run(p, "项目怎么做  ·  可复用做法", size=13, bold=True, color=GREEN)
for t in ["使用 cid 末两位做确定性路由；Apollo 权重语义保持不变。", "cid 为 null、空串、非数字时走降级策略，不让异常输入阻断主链路。", "用 00 / 49 / 50 / 99 等边界值验证，回滚就是恢复随机分流。", "复用原则：任何灰度或路由先问『同一用户是否必须稳定命中』。"]:
    p = para(tf); p.space_before = Pt(10); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=12, color=TEXT)
tf = txbox(s, Inches(0.86), Inches(6.85), Inches(11.8), Inches(0.18))
p = para(tf, True); _run(p, "来源：xiaohua_vn · openspec/changes/liveness-provider-cid-weighted-routing/", size=8.5, color=DIM, name=FONT_M)
footer(s, "Use·案例")
notes(s, "真实案例：xiaohua_vn 活体服务商确定性分流。用随机→按 cid 稳定命中的对比讲清问题、验证和回滚。")

# ---------------- 21 real case: aegis guardrails ----------------
s = new_slide()
header(s, "USE · 真实案例 04", "线上失败不是靠提醒，而是变成运行时边界", color=PINK, title_size=24)
tagline(s, "aegis 的做法很直接：把超窗、误查代码这类风险，收口到运行时接缝和工具声明里。", color=PINK)
add_box(s, Inches(0.62), Inches(2.02), Inches(6.0), Inches(4.72), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=0.75)
tf = txbox(s, Inches(0.9), Inches(2.18), Inches(5.45), Inches(0.3))
p = para(tf, True); _run(p, "发生了什么", size=13, bold=True, color=PINK)
for t in ["LKE 曾出现 input length too long；自由环还能自主查询私有 GitLab 代码。", "只写提示词提醒不够：一个是运行时边界，一个是能力暴露边界。"]:
    p = para(tf); p.space_before = Pt(10); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=12.5, color=TEXT)
add_box(s, Inches(0.9), Inches(4.32), Inches(5.35), Inches(1.72), fill=PURPLE_P, line=PURPLE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
tf = txbox(s, Inches(1.12), Inches(4.52), Inches(4.9), Inches(1.3), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True); p.alignment = PP_ALIGN.CENTER
_run(p, "失败 / 风险  →  change  →  可执行护栏", size=15, bold=True, color=WHITE)
p = para(tf); p.alignment = PP_ALIGN.CENTER; p.space_before = Pt(10)
_run(p, "问题变成仓库里的默认行为", size=11.5, color=PINK)
add_box(s, Inches(6.9), Inches(2.02), Inches(5.8), Inches(4.72), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
tf = txbox(s, Inches(7.18), Inches(2.18), Inches(5.25), Inches(0.3))
p = para(tf, True); _run(p, "项目怎么做  ·  可复用做法", size=13, bold=True, color=GREEN)
for t in ["context-window：ModelClient 缝估算预算，先丢最老 history，再收窄 userText；工具结果封顶 8,000 字符。", "code-query-human-confirmation：从自由环移除 code.lookup / code.search，只保留用户显式触发的 code.locate。", "默认关闭或受控启用，保留 fail-open / 回滚路径，避免护栏变成新故障。", "复用原则：高风险能力优先结构性收口，线上失败优先落成可配置边界。"]:
    p = para(tf); p.space_before = Pt(9); p.line_spacing = 1.1
    _run(p, "▸ " + t, size=11.3, color=TEXT)
tf = txbox(s, Inches(0.86), Inches(6.85), Inches(11.8), Inches(0.18))
p = para(tf, True); _run(p, "来源：xhproject/aegis · archive/2026-09-09-log-context-window-cap/ + archive/2026-09-09-code-query-human-confirmation/", size=8.5, color=DIM, name=FONT_M)
footer(s, "Use·案例")
notes(s, "真实案例：aegis 的上下文窗口治理与代码查询人工确认。强调结构化能力收口和运行时预算，不展开 Spring AI 内部实现。")

# ---------------- 22-24 varhub-risk cases ----------------
real_case_slide(
    "USE · varhub-risk 案例 05",
    "把 V3 SQL 变成 240+ 个可复用还款变量",
    "核心判断：大规模变量建设先守住语义，再扩展窗口、维度和消费场景。",
    CYAN,
    ["风控需要还款行为画像；V3 Hive SQL 已有口径，线上取数落到 MySQL 实时表。",
     "变量覆盖历史、近 N 期 / 月、生命周期、逾期时序、订单结构与趋势交叉。"],
    ("Stage 0 预处理  →  Stage 1 标签  →  多窗口聚合", "实时计算 · 变量包 LOAA_PRE / LOAB_PRE"),
    ["用 V3 SQL 作为语义基线，Java 侧拆成预处理、标签、聚合和结果 DTO。",
     "按 3/6/12/24/36 期、3/6/12/24/36/60 月等窗口复用同一套中间模型。",
     "修复 `as_of_date > current_repay_date` 过滤后，近 N 期与连续逾期结果不再纳入未来期次。",
     "可复用原则：先固定口径，再扩展变量数量；聚合维度必须可回溯到来源规则。"],
    "varhub-risk · openspec/changes/repay-derivative-variables/ + align-v3-sql-code-logic/",
    "varhub-risk 还款衍生变量案例：重点讲 SQL 语义基线、分阶段计算、中间模型与多窗口复用，不展开 240+ 个变量清单。"
)

real_case_slide(
    "USE · varhub-risk 案例 06",
    "跨库学历特征：静态数据进入变量中心",
    "核心判断：跨库特征的难点不在查询，而在数据所有权、身份关联和变量契约。",
    GREEN,
    ["提现审批和跑批需要学历画像，但变量中心缺少学信网离线回溯特征。",
     "数据由 DBA 落库，服务侧负责消费 4 张静态表并加工 9 个变量。"],
    ("学历 / 学籍  +  软科排名  +  985/211 标签", "identity_no_md5 关联  →  9 个类型化变量"),
    ["新增 EducationFeatureService，查询与加工集中在变量服务，不泄漏静态表细节。",
     "整数 / 字符串变量使用明确后缀和 DTO，注册后绑定 LOAA_PRE / LOAB_PRE。",
     "DBA 负责表结构与落库，服务负责读取、转换和变量口径，边界清晰。",
     "可复用原则：先定义数据 owner、关联键、空值语义，再定义变量编码。"],
    "varhub-risk · openspec/changes/education-features/",
    "varhub-risk 学历特征案例：重点讲跨数据源边界、身份关联与变量注册，不展开 4 张表的字段明细。"
)

real_case_slide(
    "USE · varhub-risk 案例 07",
    "订单标签直连三域，保持决策变量单一入口",
    "核心判断：跨域取数先固定路由语义，再把上游差异收敛成一个稳定变量。",
    ORANGE,
    ["贷中决策需要识别订单购买的是优享卡、补 16% 保险，还是未购买。",
     "事实分散在 order、rubick、datainquiry 三个域，变量中心不复制上游业务逻辑。"],
    ("order 路由  →  保险查询 / 优享卡查询", "汇聚为 ORDER_PCH_CARD_TYPE_S：0 / 1 / 2"),
    ["通过 needRedirect 固定保险 hold 路径，再调用 rubick 保险查询与 datainquiry 卡查询。",
     "新增变量，不修改既有变量和接口；Dubbo consumer 版本 / group 与上游契约对齐。",
     "已知口径误差显式记录：退保回退、划扣二态等数据缺口不伪装成精确结果。",
     "可复用原则：复杂上游在服务边界收敛为单值枚举，未知契约先标注再接入。"],
    "varhub-risk · openspec/changes/add-order-pch-card-type-var/",
    "varhub-risk 订单卡类型案例：重点讲跨域 Dubbo 依赖、路由语义、单值变量契约和已知口径误差，不展开上游实现。"
)

# ---------------- 25 review ----------------
s = new_slide()
header(s, "回顾", "这套系统现在到哪、怎么衡量、什么该上", color=GREEN)
add_box(s, Inches(0.62), Inches(1.6), Inches(6.0), Inches(2.86), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.08, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(1.72), Inches(5.6), Inches(2.6))
p = para(tf, True); _run(p, "演进到哪", size=12.5, bold=True, color=CYAN)
for t in ["从纯方法论文档 → Agent 驱动接入", "OpenSpec 为 owner + Delta Specs 演进",
          "Self-Refine 有界闭环 + 经验记忆 + Fitness",
          "需求反思 / RAM/D 先想清再写（0.4）",
          "多 Agent 与跨平台 CI（0.5）"]:
    p = para(tf); p.space_before = Pt(6); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=11.5, color=TEXT)
add_box(s, Inches(0.62), Inches(4.6), Inches(6.0), Inches(2.4), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.08, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(4.72), Inches(5.6), Inches(2.2))
p = para(tf, True); _run(p, "怎么衡量有效", size=12.5, bold=True, color=GREEN)
for t in ["改对：review 迭代↓ · 返工率↓ · 逃逸缺陷↓", "改稳：变更失败率↓ · 恢复时间↓",
          "看得清：带证据的变更占比↑ · 审计闭环",
          "省成本：稳定前缀 → prompt cache 命中↑"]:
    p = para(tf); p.space_before = Pt(6); p.line_spacing = 1.15
    _run(p, "▸ " + t, size=11.5, color=TEXT)
add_box(s, Inches(6.9), Inches(1.6), Inches(5.8), Inches(5.4), fill=AMBER_P, line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.08, line_w=1.0)
tf = txbox(s, Inches(7.12), Inches(1.75), Inches(5.4), Inches(0.3))
p = para(tf, True); _run(p, "什么项目该上 HEK", size=12.5, bold=True, color=ORANGE)
for t in ["需要稳定架构的团队 / 领域工程", "AI 已实质参与日常变更，想从生成器变伙伴",
          "关注合规 / 可审计，想证据成为资产",
          "低风险局部改动可走 light 档——方法论是默认值，不是强制每处套用"]:
    p = para(tf); p.space_before = Pt(7); p.line_spacing = 1.18
    _run(p, "▸ " + t, size=11.5, color=TEXT)
footer(s, "回顾")
notes(s, "收尾前给判断标准：何时有价值、怎么衡量、什么项目适合。强调先立 baseline 再谈收益。")

# ---------------- 26 closing ----------------
s = new_slide()
top = add_box(s, Inches(0.02), Inches(0.02), prs.slide_width - Inches(0.04), Inches(0.12), fill=GREEN)
bolt(s, int(Inches(11.15)), int(Inches(0.75)), int(Inches(0.95)), int(Inches(2.4)), color=GREEN, alpha=70, glow=False)
tf = txbox(s, Inches(0.9), Inches(0.75), Inches(9.6), Inches(0.5))
p = para(tf, True); _run(p, "写在最后 · TAKEAWAY", size=13, bold=True, color=GREEN)
tf = txbox(s, Inches(0.9), Inches(1.3), Inches(9.6), Inches(1.55))
p = para(tf, True)
_run(p, "把“人脑里的规则”，变成", size=28, bold=True, color=WHITE)
_run(p, "“仓库里的规则”", size=28, bold=True, color=CYAN)
_run(p, "。", size=28, bold=True, color=WHITE)
add_box(s, Inches(0.9), Inches(3.35), Inches(11.6), Inches(2.55), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06)
tf = txbox(s, Inches(1.2), Inches(3.52), Inches(11.0), Inches(2.2))
p = para(tf, True); _run(p, "五条结论", size=13, bold=True, color=GREEN)
for i, t in enumerate([
    "框架就五件事：原则 / 流程 / 产物 / 治理 / 反哺",
    "Agent = LLM + Harness：模型负责推理，Harness 负责上下文、权限与证据",
    "规格先于代码：proposal·spec·design·tasks，delta 合回权威库",
    "完成 = 门禁 + 证据：生成了 ≠ 做完；错误要反哺成规则",
    "落地策略：先跑通 → 再加门禁，避免一次性全配",
]):
    p = para(tf); p.space_before = Pt(6); p.line_spacing = 1.12
    _run(p, f"{i+1}. {t}", size=13.5, color=TEXT, bold=(i == 4))
chips(s, Inches(0.9), Inches(6.2), 0, ["GitHub · 8425334/harness-engineering-kit", "README.zh · AI 实战教程"],
      fill=BG2, color=CYAN, size=11.5, line=CYAN)
tf = txbox(s, Inches(0.9), Inches(6.9), Inches(11.8), Inches(0.4))
p = para(tf, True); _run(p, "分享人：沈学海   ·   ", size=11, bold=True, color=WHITE)
_run(p, "感谢聆听 · 讲的细节全部在仓库里，开箱即可实操", size=11, color=DIM)
notes(s, "收束到五条结论，重点是『先跑通再加门禁』。现场可打开 aegis，走一条代表性变更展示四件套与 Fitness。")

# ---------------------------------------------------------------- save
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Harness-Engineering-Kit-全局导览.pptx")
prs.save(out)
print("SAVED:", out)
print("SLIDES:", len(prs.slides._sldIdLst))
