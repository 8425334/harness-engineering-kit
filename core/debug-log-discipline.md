# Debug-Log Discipline

AI Agents must follow the three-phase "log → self-check → cleanup" cycle after coding to avoid implicit assumptions that can't be reproduced after commit. Unit test green ≠ behavior correct — tests only verify path coverage; log self-checks verify the **actual data flow** on those paths matches business expectations.

## Three-Phase Discipline

### Phase 1: Coding — Add Debug Logs at Key Positions

Add **temporary debug logs** at the following positions (use the most direct output: `System.out.println` / `console.log` / `print()` — no logging framework needed):

| Position | Log Content |
|----------|-------------|
| Branch entry/exit | Which branch was taken, key variable values |
| State transitions (before/after) | Status values before and after change, trigger condition |
| External call entry/exit | HTTP/RPC/DB call params, return values, duration |
| Exception paths (catch) | Exception type, message, context variables |
| Aggregate root method entry | Input params, invariant validation results within the aggregate |

Debug logs are for the agent to read and verify, not for production. They don't need to be pretty — they need high information density.

### Phase 2: Testing — Self-Check Expectations

When running unit tests, the agent must read the log output and verify item by item:

- Branch hits match expectations (correct if/else/switch branch taken)
- State transitions follow the right path (status A → B, not A → C)
- External call params/results match the contract (HTTP request fields, DB query conditions, RPC response structure)
- Exception paths are correctly triggered (exception thrown when expected, with correct type/message)

**Mismatch → go back and fix the code.** Don't let "tests are green" be enough. Passing tests only means nothing crashed; log self-checks mean the behavior is right.

### Phase 3: Cleanup — Remove Temp Logs, Keep Important Logs

After tests pass and self-checks match expectations:

| Category | Action | Examples |
|----------|--------|----------|
| Temporary debug output | **Delete** | `System.out.println`, `console.log`, `print()`, `e.printStackTrace()` |
| Framework business logs | **Keep** | `log.info("order {} dispatched", orderId)`, `log.error("payment failed", e)` |
| Framework diagnostic logs | **Keep** | `log.debug("cache miss for key {}", key)`, `log.warn("retry {} for {}", n, op)` |

**"Important log" criteria**: Records business-critical events, exception diagnostics, performance instrumentation, observability metrics — these are the basis for production troubleshooting. Temporary debug output records development-time data flow verification; once verified, it has no lasting value and must be removed.

Retained logs should have business semantics, not `log.info("here")` or `log.info("test1")` — meaningless logs are neither temporary debug nor important; rewrite them with semantics or delete them.

## Integration with Fitness

Phase 3 is enforced by `check_debug_log_cleanup.py` (see `templates/fitness/rules/debug-log-cleanup.md.template`):

- Scans changed files for residual `System.out` / `System.err` / `console.log` / `console.debug` / `debugger` / `print()` / `printStackTrace` — blocks on detection.
- Framework-level logger calls (`log.info` / `log.debug` / `logger.info` / `LOGGER.info` etc.) are **not checked** — automatically satisfy "important logs stay".

Phase 1 and Phase 2 cannot be statically verified and rely on agent discipline. The fitness gate only guarantees Phase 3 cleanup results, not that self-checks were actually performed — that's covered by code review.

## Relationship with Existing Methodology

| Existing Methodology | Relationship |
|---------------------|-------------|
| `change-lifecycle.md` | Temporary observation occurs during Apply; cleanup and evidence occur before Review passes |
| TDD (`test-driven-development`) | Phase 2 self-check extends the TDD red-green cycle — not just checking test pass/fail, but also log data flow matches expectations |
| `verification-before-completion` | Phase 3 cleanup verification is a concrete application of that skill |
| `abstraction-first.md` | Temporary debug logs don't pollute the contract layer; retained framework logs belong to the implementation layer |
