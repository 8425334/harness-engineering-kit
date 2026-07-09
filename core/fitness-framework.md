# Fitness Quality Gate Framework

Fitness is a tiered quality check system whose core purpose is to **define the AI Agent's completion conditions**. The Agent doesn't know when something is "truly done" — Fitness encodes that judgment as executable rules.

## Universal Principles

### Core Philosophy

> Rules must live in the repository. Rules must be readable by both humans and executable by scripts.

Fitness is not ancillary CI configuration — it is part of the codebase. The AI Agent can read the rules, understand constraints, and know what to fix on failure.

### Three-Tier System

| Tier | Name | Duration | Typical Checks | Trigger |
|------|------|----------|----------------|---------|
| **fast** | Fast Gate | <30s | Compile, lint, entry completeness | Every save / every Agent cycle |
| **normal** | Standard Gate | <5min | Unit tests, arch boundaries, security scan | Pre-commit |
| **deep** | Deep Gate | Unlimited | Integration tests, contract validation, perf benchmarks | CI / pre-push |

### Rule Declaration Format

Each rule is declared with Markdown frontmatter, readable by both humans and machines:

```yaml
---
dimension: <quality dimension name>
tier: fast
metrics:
  - name: <check name>
    command: <shell command>
    pattern: <optional output match regex>
    hard_gate: true/false
    tier: fast
    timeout: 300
---
```

Key fields:

- **dimension**: Quality dimension (e.g., `security`, `test-coverage`, `architecture-boundary`)
- **metrics**: List of check items under this dimension
- **hard_gate**: `true` = failure blocks the pipeline (non-zero exit code), `false` = report only
- **pattern**: If specified, match against command output; if not, only check exit code
- **timeout**: Timeout in seconds (default 300)

### Hard Gate Mechanism

Hard Gate is the "Definition of Done" for the AI Agent era:

| Type | Failure Behavior |
|------|-----------------|
| **Normal metric** | Report failure, lower score, don't block |
| **Hard Gate** | Block pipeline, exit code 2, explicitly list failures |

Normal metric failures can be fixed later ("quality degradation"); Hard Gate failures must be resolved immediately ("process terminated").

### Dimension Organization

One `.md` file per quality dimension, placed under `docs/fitness/`:

```
docs/fitness/
├── README.md              # Rule manual (overview)
├── architecture-boundary.md
├── backend-quality.md
├── security.md
├── test-coverage.md
├── sql-quality.md
├── ...
├── verification-ledger.md  # Verification ledger (records verified scenarios)
└── scripts/
    └── fitness.py           # Unified executor (zero deps, pure stdlib)
```

### Executor Design Principles

The executor (`fitness.py`) must be:
- **Zero dependencies**: Python stdlib only, no `pip install`
- **Single file**: One `.py` file is enough to run
- **Auditable**: `--dry-run` mode shows what will execute
- **Tiered**: `--tier fast|normal|deep` select depth on demand
