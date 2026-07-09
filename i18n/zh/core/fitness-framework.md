# Fitness 质量门禁框架

Fitness 是一套分层质量检查体系，核心作用是**定义 AI Agent 的完成条件**。Agent 不知道什么时候算"真正完成" — Fitness 把这个判断编码为可执行的规则。

## 通用原则

### 核心理念

> 规则必须在仓库中。规则必须既能被人阅读，也能被脚本执行。

Fitness 不是 CI 系统的附属配置，而是代码库的一部分。AI Agent 可以读取规则、理解约束、在失败时知道需要修复什么。

### 三层分级体系

| Tier | 名称 | 耗时 | 典型检查 | 触发时机 |
|------|------|------|---------|---------|
| **fast** | 快速门禁 | <30s | 编译、lint、入口完整性 | 每次保存/每次 Agent 循环 |
| **normal** | 标准门禁 | <5min | 单元测试、架构边界、安全扫描 | 提交前 / pre-commit |
| **deep** | 深度门禁 | 无限制 | 集成测试、契约验证、性能基准 | CI / pre-push |

### 规则声明格式

每条规则用 Markdown frontmatter 声明，对人和机器同时可读：

```yaml
---
dimension: <质量维度名>
tier: fast
metrics:
  - name: <检查名称>
    command: <shell 命令>
    pattern: <可选的输出匹配正则>
    hard_gate: true/false
    tier: fast
    timeout: 300
---
```

关键字段：

- **dimension**：质量维度（如 `security`、`test-coverage`、`architecture-boundary`）
- **metrics**：该维度下的检查项列表
- **hard_gate**：`true` = 失败阻断流程（非零退出码），`false` = 仅报告不阻断
- **pattern**：如果指定，从命令输出中匹配；如果不指定，只看退出码
- **timeout**：超时秒数（默认 300）

### Hard Gate 机制

Hard Gate 是 AI Agent 时代的 "Definition of Done"：

| 类型 | 失败行为 |
|------|---------|
| **普通指标** | 报告失败，降低评分，不阻断流程 |
| **Hard Gate** | 阻断流程，退出码 2，明确列出失败项 |

普通指标失败可以后续修复（"质量折损"），Hard Gate 失败必须立即解决（"流程终止"）。

### 维度组织

每个质量维度一个 `.md` 文件，放在 `docs/fitness/` 下：

```
docs/fitness/
├── README.md              # 规则手册（总体说明）
├── architecture-boundary.md
├── backend-quality.md
├── security.md
├── test-coverage.md
├── sql-quality.md
├── ...
├── verification-ledger.md  # 验证账本（记录已验证场景）
└── scripts/
    └── fitness.py           # 统一执行器（零依赖，纯 stdlib）
```

### 执行器设计原则

执行器（`fitness.py`）必须是：
- **零依赖**：只用 Python stdlib，不需要 `pip install`
- **单文件**：一个 `.py` 文件即可运行
- **可审计**：`--dry-run` 模式展示将执行什么
- **可分层**：`--tier fast|normal|deep` 按需选择深度
