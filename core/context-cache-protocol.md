# Context Cache Protocol

The Harness context cache is a repository-side protocol for making context
prefixes stable and measuring cache behavior. It does not replace or configure
the host Agent or provider cache.

## Contract

`context_cache.py fingerprint` resolves context through `resolve_context.py`,
then hashes the exact ordered bytes of the policy, profile, root index, and
selected `AI.md` files. The resulting `prefix_digest` is the only cache
identity used by the Harness adapter.

Adapters record one `hit`, `miss`, or `bypass` event per context request. Only
`hit` and `miss` are included in the hit-rate denominator. A provider that does
not expose cache telemetry must report `bypass`; it must never be treated as a
hit.

The canonical long-task target is:

```text
hit_rate = hits / (hits + misses) >= 0.995
```

The denominator, prefix digest, context file digests, provider layer, and
benchmark result are retained as evidence. A cold start is a miss and is not
silently excluded.

## Host Boundary

The adapter is invoked at context preflight, lifecycle gates, resume, and
benchmark boundaries. It does not rewrite system prompts, host configuration,
or provider settings. Claude hooks remain opt-in, and Codex uses the explicit
save/recovery path documented by the compaction templates.

Cache failure is an optimization failure, not a correctness failure. Context
resolution remains fail-closed; cache telemetry may report `bypass` when the
host cannot expose provider results.
