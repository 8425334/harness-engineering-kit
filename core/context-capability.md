# Context Capability

Context quality comes from bounded routing, not bulk loading or duplicated rules.

## Two Context Layers

| Artifact | Purpose | Hard boundary |
|---|---|---|
| Root `ai.json` | Machine-readable initialization map | Summary and routing only; ≤4096 bytes; no commands, permissions, constraints, or detailed rules |
| Indexed `AI.md` | Human- and machine-readable path detail | Responsibilities, boundaries, invariants, dependencies, entrypoints, contracts, and local verification; ≤400 lines |

There is exactly one root `ai.json`. Its root module (`path: "."`) is mandatory. Every maintained `AI.md` must be registered in its `modules` array with a module path, short summary, exact context path, and 1–8 `read_when` keywords. Before code work, `resolve_context.py` resolves every task path and explicit keyword into one deterministic load order: policy, methodology profile, index, then selected details from parent to child. Child details contain only local differences; ancestor details remain applicable. Neither layer can override native instructions or `agent-policy.yaml`.

Resolution fails closed when the root route is absent, a target escapes the project, an explicit keyword has no route, or any indexed document is invalid. Path selection includes every indexed ancestor of the target. Keyword selection includes every matching module and its indexed ancestors.

## Update Contract

Every non-trivial change includes approval-bound `context-impact.json`:

- `project-summary`, `module-topology`, `context-route`, `entrypoint` require `ai.json` updates.
- `responsibility`, `boundary`, `invariant`, `dependency`, `contract`, `local-verification` require affected `AI.md` updates.
- `none` is valid only by itself and still requires reasons for both layers.
- `analyzed_paths` declares the complete planned deliverable file set. Review digests must match it exactly.

`check_context_docs.py` validates schema, size, path containment, index completeness, detail structure, and missing references. `resolve_context.py` proves that the validated graph produces an executable load order. `check_phase.py` prevents Review from passing when required context updates are absent or unapproved.

Signal selection is a semantic design decision bound into approval; deterministic gates verify its mapping and evidence but cannot infer business responsibility from arbitrary code. The approver must reject an unjustified `none` decision.

Preserve decisions and evidence in the change workspace across compaction or handoff. Measure wrong-assumption rate, loading time, repeated reads, intervention rate, and cost/latency; provider caching is an optimization, not a correctness guarantee.

The repository-side cache contract is defined in
[Context Cache Protocol](context-cache-protocol.md). It stabilizes the ordered
context prefix and records provider-reported `hit`, `miss`, or `bypass`
outcomes. It does not change host Agent configuration or claim provider cache
behavior without telemetry.

The repository-side cache contract is defined in
[Context Cache Protocol](context-cache-protocol.md). It stabilizes the ordered
context prefix and records provider-reported `hit`, `miss`, or `bypass`
outcomes. It does not change host Agent configuration or claim provider cache
behavior without telemetry.
