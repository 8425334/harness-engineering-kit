# Fitness Quality Gate Framework

Fitness is a tiered quality check system whose core purpose is to **define the AI Agent's completion conditions**. The Agent doesn't know when something is "truly done" — Fitness encodes that judgment as executable rules.

## Universal Principles

### Core Philosophy

> Rules must live in the repository. Rules must be readable by both humans and executable by scripts.

Fitness is not ancillary CI configuration — it is part of the codebase. The AI Agent can read the rules, understand constraints, and know what to fix on failure.

### Protected Control Plane

Project Agents may read and execute `docs/fitness/**`, but must not modify it. There is no change-size exemption: adding, editing, renaming, or deleting any protected file requires external human approval bound to the exact change digest. The only automatic exceptions are canonical first installation when the baseline has no Fitness directory, and a demonstrable repair where every changed file is an existing Python file that fails baseline parsing and passes after the repair.

`check_fitness_protection.py` compares the working tree with `HEAD`, or with `--base` / `FITNESS_BASE_REF` in CI. Approval metadata must come from a protected human/CI workflow through `FITNESS_CHANGE_APPROVED_BY`, `FITNESS_CHANGE_APPROVAL_SOURCE`, `FITNESS_CHANGE_APPROVAL_ID`, and the exact `FITNESS_CHANGE_APPROVAL_DIGEST` printed by the blocked check. The digest binds approval to the base commit, complete changed-path set, status, and resulting content. The script proves integrity, not human identity; branch protection and CI permissions must prevent pull-request code from supplying approval variables.

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
