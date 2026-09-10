# -*- coding: utf-8 -*-
# Patch1: add tagline helper + delete stale fullstack page
import io

p = "build_hek_deck.py"
src = io.open(p, encoding="utf-8").read()

# ---- 1) add tagline helper before notes() ----
anchor = "def notes(slide, text):\n    slide.notes_slide.notes_text_frame.text = text\n"
helper = '''def tagline(slide, text, color=CYAN, y=1.44, h=0.44):
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
'''
assert anchor in src, "notes anchor missing"
src = src.replace(anchor, helper, 1)

# ---- 2) delete stale fullstack page (marker 17 fullstack before 18 requirement reflection) ----
start_marker = "# ---------------- 17 fullstack ----------------"
end_marker = "# ---------------- 18 requirement reflection ----------------"
i = src.index(start_marker)
j = src.index(end_marker)
src = src[:i] + src[j:]

io.open(p, "w", encoding="utf-8").write(src)
print("patch1 OK: helper added + stale fullstack removed")