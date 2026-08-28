# Context Capability & Prompt Caching

Context capability is the engineering discipline of keeping the model's context window lean, relevant, persistent, and cheap to reuse. This document teaches two linked ideas: the **prompt-caching prefix invariant** — the mechanism by which a docs-based methodology achieves ~99%+ prompt-cache hit rates — and a **five-dimension model** for engineering context capability.

## Universal Principles

### A. The Prompt Caching Prefix Invariant

LLM prompt caching (Anthropic's server-side cache) is a **byte-exact prefix match**. The cache key is derived from the exact rendered prompt bytes up to each `cache_control` breakpoint. Any byte change anywhere in the prefix invalidates everything after it. Render order is `tools → system → messages`.

```
[ tools ][ system ][ messages 1..n ]          ← the byte-exact prefix
      └────────────────┬────────────────┘
any byte change here → everything after is recomputed (cache miss)
```

In an agentic coding loop, each request is nearly identical to the previous one: the whole prior conversation plus a small delta (Δ) of new assistant text and tool results. Per-request hit rate is therefore:

```
hit rate ≈ (total − Δ) / total
```

which approaches 100% as the conversation grows — **provided the prefix is never rewritten**.

Three properties of a docs-based methodology keep the prefix stable:

| Mechanism | What it preserves | Why it prevents cache misses |
|-----------|-------------------|------------------------------|
| Frozen system prompt | CLAUDE.md / AI.md loaded deterministically and versioned | Byte-identical system prompt every request → hits from the first request |
| Low context churn → rare compaction | The un-compacted conversation prefix | Compaction / summarization rewrites history → full cache invalidation; docs act as a map so reads are targeted and deltas stay small |
| Deterministic workflow ordering | A predictable tool-call sequence | Fewer, consolidated tool calls stay inside the 20-block lookback window a cache breakpoint can traverse |

Cache economics: the session-level hit rate is `cache_read / (input + cache_creation + cache_read)`; the residual is the per-request fresh delta. Cache reads bill at roughly 0.1× the base input price, so a ~99% hit rate means cost and latency are dominated by cheap cache reads.

### B. Five-Dimension Context Capability Model

| # | Dimension | Mnemonic | Solves |
|---|-----------|----------|--------|
| 1 | Window & Compression | 装得下 | Context that runs out of room |
| 2 | Cross-Session Memory | 记得住 | Context that is lost between sessions |
| 3 | Injection Precision | 装得准 | Context that is too broad to be useful |
| 4 | Caching Efficiency | 用得省 | Context that is repeatedly re-processed at full price |
| 5 | Reasoning Depth per Token | 想得深 | Output quality per token consumed |

#### 1. Window & Compression（装得下）

The window has to fit the work. Use large-context models where available; let the harness compact when the window fills; prefer **context editing** (clearing stale tool results and completed thinking) over summarization when stale content is the problem — editing prunes, summarization rewrites. See `harness-engineering.md` Component 5 for the compaction-preservation pattern that keeps an in-flight round alive across a compaction event.

#### 2. Cross-Session Memory（记得住）

Persist what must survive the session: facts go to the persistent memory system; the in-flight round goes to the round contract (`harness-engineering.md` Component 5, deployables in `templates/compaction/`); long-term decisions live in plans and specs (`mandatory-skills.md` — OpenSpec, Superpowers) instead of being held in-context. The rule: anything the agent must still know tomorrow should be a file, not a conversation.

#### 3. Injection Precision（装得准）

Put the right context in, and no more. Path documents give the agent a map; codegraph gives symbol-level retrieval instead of whole-file dumps (`mandatory-skills.md`); subagents act as condensers — read broadly, return only conclusions; skills lazy-load their bodies; tool search loads only the schemas that matter. Every byte you keep out of the window is a byte you do not re-process.

#### 4. Caching Efficiency（用得省）

Once context is in, make re-use cheap. Freeze the system prompt (docs are deterministic, versioned). Never rewrite the top-level system prompt mid-session — append a mid-conversation system message instead:

```json
{"role": "system", "content": "Update: order-service boundary finalized"}
```

Pre-warm with `max_tokens: 0`; choose a 1-hour TTL when traffic has gaps; keep ≤ ~15 tool-call blocks per turn so the cache breakpoint stays within its 20-block lookback window; never switch models or tools mid-session (caches are model- and tool-scoped).

#### 5. Reasoning Depth per Token（想得深）

Within a fixed budget, get more out of each token: adaptive thinking plus effort levels let the model think deeper when it matters; structured outputs keep responses compact and reusable; programmatic tool calling runs pipelines in a sandbox so only the final output returns to the window.

## Relationship with Existing Methodology

| Document | Relationship |
|----------|--------------|
| `harness-engineering.md` | Component 5 (compaction preservation) is the cross-session-memory and loss-mitigation half; this document adds the prefix invariant and the full five-dimension model |
| `mandatory-skills.md` | Codegraph is the injection-precision tool; OpenSpec / Superpowers externalize long-term context out of the window |
| `sdd-workflow.md` | Specs live outside the window; the agent reads only what the task needs → small per-request deltas |
