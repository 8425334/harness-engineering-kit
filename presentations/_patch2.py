# -*- coding: utf-8 -*-
# Patch2 (fixed): insert 5 aegis case pages each at its own position
import io
p = "build_hek_deck.py"
src = io.open(p, encoding="utf-8").read()

def insert_before(src, marker, block):
    assert marker in src, "marker missing: " + marker
    return src.replace(marker, block + marker, 1)

# ============ 7b OPENSPEC 实例 ============
b7b = '''
# ---------------- 7b openspec example ----------------
s = new_slide()
header(s, "WHAT · OpenSpec · 实例", "aegis 真实变更：能力规格先审 · 方案先批 · 任务勾选出证据", color=CYAN)
tagline(s, "一句话记住：一个 change＝规格增量（WHEN/THEN）先审 → 方案（design）先批 → 任务（tasks）勾选出证据——它们的起点都是规格，不是代码。", color=CYAN)
add_box(s, Inches(0.62), Inches(1.98), Inches(6.5), Inches(4.42), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.04, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(2.1), Inches(6.1), Inches(0.3))
p = para(tf, True); _run(p, "aegis 真实 change：capability-driven-ai-platform", size=10.5, bold=True, color=CYAN)
tree = [
    "openspec/changes/",
    "  └ 2026-09-02-capability-driven-ai-platform/",
    "      ├ proposal.md           为什么做 · 范围与影响",
    "      ├ specs/capability-planner/ spec.md      WHEN/THEN",
    "      ├ specs/capability-metadata/spec.md      能力元数据",
    "      ├ specs/capability-observability/spec.md 可观测",
    "      ├ specs/capability-routing/spec.md       路由",
    "      ├ design.md            6 模块技术方案 · 取舍 · 决策",
    "      └ tasks.md             任务分解与勾选 · 唯一进度源",
    "",
    "同仓：log-analysis-closed-loop/ = proposal·spec·design·tasks 四件套",
]
tf = txbox(s, Inches(0.86), Inches(2.48), Inches(6.1), Inches(3.8))
first = True
for ln in tree:
    par = para(tf, first); first = False
    par.space_after = Pt(2.6); par.line_spacing = 1.0
    c = MUTED if ln.startswith("  └") else (CYAN if ("spec.md" in ln) else TEXT)
    _run(par, ln, size=8.7, color=c, name=FONT_M)
def _ex_card(x, y, title, lines, acc):
    add_box(s, Inches(x), Inches(y), Inches(5.85), Inches(1.4), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.08, line_w=0.75)
    add_box(s, Inches(x), Inches(y), Inches(0.07), Inches(1.4), fill=acc, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.5)
    tf = txbox(s, Inches(x + 0.2), Inches(y + 0.1), Inches(5.5), Inches(1.22))
    p = para(tf, True); _run(p, title, size=11, bold=True, color=acc)
    p = para(tf); p.space_before = Pt(3); p.line_spacing = 1.1
    _run(p, lines, size=10, color=TEXT)
_ex_card(7.42, 1.98, "规格分文件，评审可 diff", "proposal 一句话立界；能力规格按模块拆成多份 WHEN/THEN，每条独立评审、天然可 diff。", CYAN)
_ex_card(7.42, 3.5, "design 是给人批的方案包", "6 模块共享一份 design.md：目标架构 · 职责 · 时序 · 接口 · 波次 · 残留风险，审批后才进 Apply。", GREEN)
_ex_card(7.42, 5.02, "tasks 是唯一进度源", "任务勾选必须对应一次成功执行，证据写回 execution-evidence.json，归档全文可审计。", ORANGE)
add_box(s, Inches(0.62), Inches(6.52), Inches(12.26), Inches(0.6), fill=CYAN_P, line=CYAN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14, line_w=1.0)
tf = txbox(s, Inches(0.86), Inches(6.52), Inches(11.8), Inches(0.6), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True)
_run(p, "同一次变更里：规格分为多份、设计一件、任务一件——四件各司其职，这就是 OpenSpec 在真实仓库里的样子。", size=11, bold=True, color=CYAN)
footer(s, "What · OpenSpec 实例")
notes(s, "用 aegis 真实 change 证明 OpenSpec。capability-driven-ai-platform 把一个平台能力拆成 proposal + 4 份能力规格 + design + tasks；同仓 log-analysis-closed-loop 是标准四件套。右三卡讲清四件套各司其职：规格分文件可评审、design 给人批、tasks 出证据。")
'''

# ============ 8b 上下文实例 ============
b8b = '''
# ---------------- 8b context example ----------------
s = new_slide()
header(s, "WHAT · 上下文 · 实例", "aegis 真实落地：8 个模块 8 份 AI.md，改到哪只加载哪", color=CYAN)
tagline(s, "一句话记住：上下文不靠全塞，而靠『机器索引路由 + 路径级精读』——每个子模块一份 AI.md，只加载命中的那层。", color=CYAN)
add_box(s, Inches(0.62), Inches(1.98), Inches(5.5), Inches(4.5), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.05, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(2.1), Inches(5.0), Inches(0.3))
p = para(tf, True); _run(p, "根 ai.json（≤4096B）路由到模块 AI.md", size=10.5, bold=True, color=CYAN)
mods = ["根 AI.md（全仓）", "aegis-core / AI.md (内核纯契约)", "aegis-runtime / AI.md (执行器)", "aegis-ai-spring / AI.md (模型 seam)", "aegis-intent / AI.md (意图)", "aegis-agent / AI.md (supervisor·log)", "aegis-channel / AI.md (飞书·网页)", "aegis-common / AI.md (共享)", "aegis-application / AI.md (入口)"]
tf = txbox(s, Inches(0.86), Inches(2.5), Inches(5.1), Inches(3.9))
first = True
for m in mods:
    par = para(tf, first); first = False
    par.space_after = Pt(4); par.line_spacing = 1.05
    _run(par, "▸ ", size=10, bold=True, color=CYAN)
    _run(par, m, size=10, color=TEXT, name=FONT_M if "/" in m else FONT)
add_box(s, Inches(0.62), Inches(6.5), Inches(5.5), Inches(0.62), fill=AMBER_P, line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.14, line_w=1.0)
tf = txbox(s, Inches(0.86), Inches(6.5), Inches(5.1), Inches(0.62), anchor=MSO_ANCHOR.MIDDLE)
p = para(tf, True)
_run(p, "Fail-closed：缺任一层 → 拒绝开工，不带残缺上下文", size=10.5, bold=True, color=ORANGE)
add_box(s, Inches(6.5), Inches(1.98), Inches(6.2), Inches(3.08), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.07, line_w=1.0)
tf = txbox(s, Inches(6.72), Inches(2.1), Inches(5.8), Inches(0.3))
p = para(tf, True); _run(p, "每份 AI.md 只答四件事（aegis-core 实样）", size=11, bold=True, color=GREEN)
ai = [
    ("Scope", "governs aegis-core —— 平台内核（纯 Java 契约）"),
    ("Responsibilities", "core/agent 契约 · core/routing 端口 · 单测"),
    ("Boundaries", "禁止 Spring/web/数据导入；只依赖 JDK"),
    ("Verification", "./mvnw -pl aegis-core test + fitness --tier fast"),
    ("Navigation", "入口点 · 关联契约 · Owner"),
]
tf = txbox(s, Inches(6.72), Inches(2.5), Inches(5.8), Inches(2.5))
first = True
for k, v in ai:
    par = para(tf, first); first = False
    par.space_after = Pt(4); par.line_spacing = 1.06
    _run(par, k, size=10, bold=True, color=GREEN, name=FONT_M)
    _run(par, "  " + v, size=10, color=TEXT)
add_box(s, Inches(6.5), Inches(5.25), Inches(6.2), Inches(1.9), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.07, line_w=0.75)
tf = txbox(s, Inches(6.72), Inches(5.38), Inches(5.8), Inches(1.68))
p = para(tf, True); _run(p, "上下文声明式化的里程碑", size=11, bold=True, color=WHITE)
for t in ["skill-declarative-loading：skill.yaml 元数据 = 唯一真相，Skill 只承载 execute()",
          "『哪些上下文进 prompt』由描述符声明，而非模型临场乱取",
          "路径级 + 声明式：改哪个模块，才加载哪个模块的规则"]:
    p = para(tf); p.space_before = Pt(4.5); p.line_spacing = 1.1
    _run(p, "▸ " + t, size=10.3, color=TEXT)
footer(s, "What · 上下文实例")
notes(s, "题落到 aegis：根 ai.json 是机器可读项目地图，按路径路由到 8 个模块各自的 AI.md，只加载命中的那层。AI.md 结构固定四件事（Scope/Responsibilities/Boundaries/Verification），来自 aegis-core 真值。skill-declarative-loading 让上下文选取声明式化。呼应 fail-closed。")
'''

# ============ 11b 规格演进实例 ============
b11b = '''
# ---------------- 11b delta example ----------------
s = new_slide()
header(s, "HOW · 规格演进 · 实例", "aegis 权威规格库 30+ 份：只能经『走完生命周期的变更』来长", color=PURPLE)
tagline(s, "一句话记住：权威 specs 始终描述『当前系统』——进行中的想法只活在 change 的增量里，合回才算数。", color=PURPLE)
add_box(s, Inches(0.62), Inches(1.98), Inches(6.0), Inches(4.55), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.04, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(2.1), Inches(5.6), Inches(0.3))
p = para(tf, True); _run(p, "openspec/specs/ · 权威库（真实 30+ 份节选）", size=10.5, bold=True, color=PURPLE)
specs = [
    "feishu-card-streaming / feishu-channel / website-channel",
    "feishu-streaming-interaction / session-management",
    "agent-runtime / agent-routing / multi-agent",
    "capability-planner / capability-metadata / capability-routing",
    "capability-observability / log-analysis / log-analysis-closed-loop",
    "cls-log-fetch / log-context-window / log-payload-boundary",
    "model-provider / model-rate-limit / model-context-window",
    "skill-declarative-loading / skill-runtime / tool-runtime",
    "intent-classification / code-location / task-orchestration",
    "",
    "每一份都对应一次已走完生命周期的变更，",
    "没有『半截』规格混在权威库里。",
]
tf = txbox(s, Inches(0.86), Inches(2.5), Inches(5.6), Inches(3.9))
first = True
for ln in specs:
    par = para(tf, first); first = False
    par.space_after = Pt(2.6); par.line_spacing = 1.02
    _run(par, ln, size=8.8, color=MUTED if (ln.startswith("每") or ln.startswith("没有")) else TEXT, name=FONT_M)
add_box(s, Inches(6.9), Inches(1.98), Inches(5.8), Inches(4.55), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.07, line_w=1.0)
tf = txbox(s, Inches(7.12), Inches(2.1), Inches(5.4), Inches(0.3))
p = para(tf, True); _run(p, "权威库怎么『长』出来（change → 合回）", size=11, bold=True, color=GREEN)
maps = [
    ("log-analysis-closed-loop", "→ log-analysis-closed-loop / spec.md", "闭环从草案变权威"),
    ("capability-driven-ai-platform", "→ capability-* ×4 / spec.md", "一次变更长出一组能力规格"),
    ("intent-aware-routing", "→ intent-classification / spec.md", "路由意图固化成总线规格"),
    ("website-channel", "→ website-channel / spec.md", "新渠道接入即入权威"),
]
tf = txbox(s, Inches(7.12), Inches(2.5), Inches(5.4), Inches(3.9))
first = True
for ch, sp, note in maps:
    par = para(tf, first); first = False
    par.space_after = Pt(2.5); par.line_spacing = 1.06
    _run(par, ch, size=9.5, bold=True, color=CYAN, name=FONT_M)
    par = para(tf); par.line_spacing = 1.0
    _run(par, "   " + sp, size=9, color=GREEN, name=FONT_M)
    par = para(tf); par.space_after = Pt(9); par.line_spacing = 1.0
    _run(par, "   " + note, size=9, color=MUTED)
footer(s, "How · 规格演进实例")
notes(s, "规格演进落到 aegis：权威 specs 库 30+ 份，每一份都是某次走完生命周期的变更合回的。右图给『变更→权威规格』四条真实增长线：日志闭环、能力驱动、意图感知、网站渠道。权威库永不描述进行中想法，Verify→Sync 通过才合回——仓库不存在半成品规格。")
'''

# ============ 13b Design 门禁实例 ============
b13b = '''
# ---------------- 13b design example ----------------
s = new_slide()
header(s, "HOW · Design 门禁 · 实例", "capability-driven-ai-platform：6 模块方案，先审后码再授权", color=PURPLE)
tagline(s, "一句话记住：design.md 是『给开发者确认的方案包』——架构·职责·时序·接口·波次·风险，审批前一行实现都不写。", color=PURPLE)
add_box(s, Inches(0.62), Inches(1.98), Inches(6.3), Inches(2.62), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(2.1), Inches(5.9), Inches(0.3))
p = para(tf, True); _run(p, "该 change 的 design.md 覆盖（对应概念页要素）", size=10.5, bold=True, color=PURPLE)
dst = ["目标架构：capability 层如何在 6 模块间织入",
       "职责/边界：谁能声明能力、谁能路由、谁能规划",
       "时序/数据流：请求 → 能力解析 → 规划 → 校验 → 执行",
       "接口契约：CapabilityTemplate · PlanDTO · 错误码",
       "实现波次 + 残留风险 + 回滚 + 开发者确认清单 C1…Cn"]
tf = txbox(s, Inches(0.86), Inches(2.48), Inches(5.9), Inches(2.0))
first = True
for t in dst:
    par = para(tf, first); first = False
    par.space_after = Pt(5); par.line_spacing = 1.1
    _run(par, "▸ " + t, size=10.2, color=TEXT)
add_box(s, Inches(0.62), Inches(4.82), Inches(6.3), Inches(2.24), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.07, line_w=1.0)
tf = txbox(s, Inches(0.86), Inches(4.94), Inches(5.9), Inches(2.05))
p = para(tf, True); _run(p, "Design 门禁三步，在这条变更里", size=11, bold=True, color=GREEN)
for t in ["① 结构校验：proposal / spec×4 / design / tasks 齐备、schema 合法",
          "② 开发者确认：把推荐方案 + 边界 + 波次 + 风险呈现出来请求确认",
          "③ 审批绑定：外部审批记录 + 契约摘要 → Apply 才被授权"]:
    p = para(tf); p.space_before = Pt(5); p.line_spacing = 1.12
    _run(p, t, size=10.5, color=TEXT)
add_box(s, Inches(7.15), Inches(1.98), Inches(5.6), Inches(5.08), fill=AMBER_P, line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.06, line_w=1.0)
tf = txbox(s, Inches(7.38), Inches(2.1), Inches(5.2), Inches(0.3))
p = para(tf, True); _run(p, "如果跳过 Design 门禁直接写码", size=11, bold=True, color=ORANGE)
for t in ["能力规划写哪、模块边界交给谁——边写边拍脑袋",
          "Spec/Design/任务图一变，原审批悄悄失效无人知",
          "『批过=永远有效』：架构漂移没被拦截，越走越失控",
          "6 模块并行时没有统一契约，各写各的正交不了",
          "没有波次与回滚：出问题只能整体回退"]:
    p = para(tf); p.space_before = Pt(6); p.line_spacing = 1.12
    _run(p, "✕ " + t, size=10.5, color=TEXT)
footer(s, "How · Design 门禁实例")
notes(s, "Design 门禁不是抽象要求：capability-driven-ai-platform 这条真实变更里，design.md 要同时回答目标架构、职责边界、时序数据流、接口契约、实现波次。三步串联：结构校验 → 开发者确认 → 审批绑定。右反向对照跳过门禁的后果，让『先设计后审批』从口号变成真实 change 上可指认的操作。")
'''

# ============ 19b 反哺实例 ============
b19b = '''
# ---------------- 19b growth example ----------------
s = new_slide()
header(s, "GROW · 反哺 · 实例", "aegis 迭代史：修复与重构 change，就是反哺机制在跑", color=PINK)
tagline(s, "一句话记住：反哺不是口号——archive 里那些 fix / refactor / 边界类变更，每条都是从失败到预防的一环。", color=PINK)
add_box(s, Inches(0.62), Inches(1.98), Inches(6.2), Inches(4.5), fill=PANEL, line=BORDER_D, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.05, line_w=0.75)
tf = txbox(s, Inches(0.86), Inches(2.1), Inches(5.8), Inches(0.3))
p = para(tf, True); _run(p, "archive 里的养成型变更（真实）", size=10.5, bold=True, color=PINK)
gr = ["traceid-extraction-fix        取 traceId 修正",
      "cls-query-cql-refactor        CLS 查询重构",
      "gitlab-read-efficiency        读效率优化",
      "code-query-human-confirmation 代码查询人工确认",
      "log-payload-boundary-capping  日志负载边界",
      "model-token-budget-gate       token 预算门禁",
      "log-context-window-cap        上下文窗上限",
      "capability-planning-hardening 能力规划加固"]
tf = txbox(s, Inches(0.86), Inches(2.5), Inches(5.8), Inches(3.9))
first = True
for ln in gr:
    par = para(tf, first); first = False
    par.space_after = Pt(5.5); par.line_spacing = 1.0
    _run(par, "▸ ", size=9.5, bold=True, color=PINK)
    _run(par, ln, size=9.5, color=TEXT, name=FONT_M)
add_box(s, Inches(7.1), Inches(1.98), Inches(5.6), Inches(4.5), fill=GREEN_P, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.07, line_w=1.0)
tf = txbox(s, Inches(7.32), Inches(2.1), Inches(5.2), Inches(0.3))
p = para(tf, True); _run(p, "失败 → 修复变更 → 预防（三条真线）", size=11, bold=True, color=GREEN)
lines = [
    ("token 超预算 / 上下文超窗", "model-token-budget-gate + log-context-window-cap", "进 Fitness 规则：预算/窗越界即拦"),
    ("日志负载太大拖垮分析", "log-payload-boundary-capping", "固化成 log-payload-boundary 权威规格"),
    ("代码查询不问人、误读", "code-query-human-confirmation", "Read 阶段人工确认成护栏"),
]
tf = txbox(s, Inches(7.32), Inches(2.5), Inches(5.2), Inches(3.9))
first = True
for fail, fix, prev in lines:
    par = para(tf, first); first = False
    par.space_after = Pt(2.5); par.line_spacing = 1.05
    _run(par, "失败事件 → ", size=10, bold=True, color=ORANGE); _run(par, fail, size=10, color=TEXT)
    par = para(tf); par.line_spacing = 1.05
    _run(par, "修复变更 → ", size=10, bold=True, color=PINK); _run(par, fix, size=10, color=TEXT, name=FONT_M)
    par = para(tf); par.space_after = Pt(10); par.line_spacing = 1.05
    _run(par, "升级预防 → ", size=10, bold=True, color=GREEN); _run(par, prev, size=10, color=TEXT)
footer(s, "Grow · 反哺实例")
notes(s, "反哺机制用真实迭代史证明：aegis archive 里有大量养成型变更。右图把三条连成『失败事件→修复变更→预防』：token 超预算→token 预算门禁→Fitness；日志大负载→负载边界→权威规格；代码查询→人工确认→护栏。正好对应 GROW 三段 + Fitness：经验被反复验证后升级成硬门禁。")
'''

for block, marker in [
    (b7b, "# ---------------- 8 context loading ----------------"),
    (b8b, "# ---------------- 9 token cache ----------------"),
    (b11b, "# ---------------- 12 governance loop ----------------"),
    (b13b, "# ---------------- 14 apply evidence ----------------"),
    (b19b, "# ---------------- 20 lesson memory ----------------"),
]:
    src = insert_before(src, marker, block)

io.open(p, "w", encoding="utf-8").write(src)
print("patch2 OK: 5 case pages inserted, each at its position")