# Context Update Decisions

Root `ai.json` is a compact routing index, never a second policy file. It contains only the project summary, module paths, short module summaries, `read_when` keywords, referenced `AI.md` paths, and canonical entrypoints. Keep it within 4096 bytes.

Indexed `AI.md` files contain detailed local responsibilities, boundaries, invariants, dependencies, entrypoints, contracts, and verification guidance. They remain supplemental to native instructions and `agent-policy.yaml`.

Every non-trivial change must complete `context-impact.json` before approval:

- Update `ai.json` for `project-summary`, `module-topology`, `context-route`, or `entrypoint` changes.
- Update affected `AI.md` files for `responsibility`, `boundary`, `invariant`, `dependency`, `contract`, or `local-verification` changes.
- Use `none` alone only when neither layer changes, and explain both decisions.
- List every planned deliverable file in `analyzed_paths`. Review file digests must match that set exactly.

Run `check_context_docs.py` after context changes. Adding an `AI.md` without indexing it, duplicating detailed rules into `ai.json`, exceeding size limits, or omitting a required context file from Review blocks the lifecycle.
