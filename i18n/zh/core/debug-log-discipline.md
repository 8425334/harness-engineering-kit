# 调试日志纪律 (Debug-Log Discipline)

AI Agent 在编码后必须经过"打日志 → 自检 → 清理"三阶段，避免提交后无法复现的隐式假设代码。单元测试通过 ≠ 行为正确 —— 测试只验证了路径覆盖，日志自检验证的是路径上的**实际数据流**是否符合业务预期。

## 三阶段纪律

### 阶段 1：编码 — 关键位置打调试日志

在以下位置强制打**临时调试日志**（用最直接的输出方式：`System.out.println` / `console.log` / `print()`，不需要走日志框架）：

| 位置 | 日志内容 |
|------|----------|
| 分支判断入口/出口 | 命中哪个分支、关键变量值 |
| 状态流转前后 | status 变更前后的值、触发条件 |
| 外部调用入口/出口 | HTTP/RPC/DB 调用的入参、返回值、耗时 |
| 异常路径 (catch) | 异常类型、消息、上下文变量 |
| 聚合根方法入口 | 入参、聚合内不变量校验结果 |

调试日志的目的是让 agent 自己能读、能核对，不是给生产环境看的。所以**不需要漂亮，需要信息密度高**。

### 阶段 2：测试 — 自检预期一致

跑单元测试时，agent 必须读取日志输出，逐条核对：

- 分支命中是否符合预期（命中了正确的 if/else/switch 分支）
- 状态流转是否走对路径（status 从 A → B 而非 A → C）
- 外部调用的入参/返回是否符合契约（HTTP 请求体字段、DB 查询条件、RPC 返回结构）
- 异常路径是否被正确触发（应该抛异常时确实抛了，且异常类型/消息正确）

**不符合预期 → 回到代码修正**，不要"测试绿了"就放过。测试通过只代表没崩，日志自检才代表行为对。

### 阶段 3：清理 — 删除临时调试日志，保留重要日志

测试通过、自检符合预期后：

| 类别 | 处理 | 例子 |
|------|------|------|
| 临时调试输出 | **删除** | `System.out.println`、`console.log`、`print()`、`e.printStackTrace()` |
| 框架级业务日志 | **保留** | `log.info("order {} dispatched", orderId)`、`log.error("payment failed", e)` |
| 框架级诊断日志 | **保留** | `log.debug("cache miss for key {}", key)`、`log.warn("retry {} for {}", n, op)` |

**"重要日志"的判定**：记录的是业务关键事件、异常诊断、性能埋点、可观测性指标 —— 这些是生产环境排障的依据，不能删。临时调试输出记录的是开发期核对数据流，验证完就失去价值，必须删。

保留的日志应该有业务语义，不是 `log.info("here")` 或 `log.info("test1")` —— 这种无意义日志既不是临时调试也不是重要日志，属于噪音，应该改写成有语义的或删除。

## 与 fitness 的衔接

阶段 3 由 `check_debug_log_cleanup.py` 门阀强制执行（详见 `templates/fitness/rules/debug-log-cleanup.md.template`）：

- 扫描变更文件，发现残留的 `System.out` / `System.err` / `console.log` / `console.debug` / `debugger` / `print()` / `printStackTrace` 即阻断。
- 框架级 logger 调用（`log.info` / `log.debug` / `logger.info` / `LOGGER.info` 等）**不纳入检查** —— 自动满足"重要日志无需删除"。

阶段 1 和阶段 2 不可静态校验，依赖 agent 自律。fitness 门阀只保证阶段 3 的清理结果，不保证清理前确实自检过 —— 这部分由代码 review 兜底。

## 与现有方法论的衔接

| 现有方法论 | 关系 |
|------------|------|
| `change-lifecycle.md` | 临时观测发生在 Apply；清理和证据在 Review 通过前完成 |
| TDD (`test-driven-development`) | 阶段 2 的自检是 TDD 红绿循环的扩展 —— 不仅看测试红绿，还要看日志数据流符合预期 |
| `verification-before-completion` | 阶段 3 的清理验证是该 skill 的具体应用 |
| `abstraction-first.md` | 临时调试日志不污染契约层；清理后保留的框架日志属于实现层 |
