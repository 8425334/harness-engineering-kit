# 自修复与运行环境完整性

自修复让 Harness 控制面在**用户对话过程中**保持可用。它是针对三类故障的有界恢复路径，不是第二套安装器，也不是绕过门禁的手段。

| 故障类别 | 典型现象 | 修复归属 |
|---|---|---|
| `engineering` Skill 未加载 | Agent 找不到或无法选择该 Skill，或其文件缺失、过期 | 从 Kit 重新同步 Skill 目录 |
| Python 环境/依赖问题 | 没有可用的 Python 3、解释器低于支持版本，或已安装的控制脚本无法编译 | 解释器需人工处理；脚本由 Kit 重新同步 |
| HEK 不完整 | 规范核心文档、控制脚本、工作流模板、OpenSpec schema、工作区目录或 `docs/methodology/VERSION` 缺失；安装版本漂移 | 从 Kit 同步规范资源 |

修复逻辑只实现一次：`scripts/repair.py`。通过 `hek repair`（执行修复）与 `hek doctor`（只读诊断）触发，安装后位于 `docs/methodology/scripts/repair.py`。

## 不变量

- **默认只读。** 诊断不写任何文件；只有 `--apply` 才会恢复文件，且逐项幂等执行，单个资源失败不会回滚其它修复。
- **只写规范资源。** 修复只写规范方法论、控制脚本、工作流模板、OpenSpec schema 和项目内 `engineering` Skill，绝不覆盖已存在的项目事实文件。
- **不改动宿主。** 不安装解释器、运行时或依赖包，不写项目根目录之外的路径；不重写已存在的 `docs/fitness/**` 基线（受保护文件缺失会记为 `manual` 发现项），只有在完全没有基线时才安装规范 Fitness 脚手架；缺少宿主前置条件时以 `manual` 报告并给出确切补救命令。
- **不降级。** 已安装版本高于 Kit 时报告不一致并停止。
- **不猜测来源。** Kit 路径（onboarding 记录或用户指定）不可用时停止并询问，绝不下载或臆造来源。
- **留痕。** 每次 apply 都会写入 `docs/methodology/repair.json`，包含环境、发现项、计划恢复、逐项结果和修复后校验。

## 发现项模型

每个发现项包含稳定的 `id`、`area`、`severity`、有上限的示例列表和可选的 `remedy`。

| severity | 含义 | Agent 行动 |
|---|---|---|
| `repairable` | 可由 `--apply` 从 Kit 恢复 | 展示计划、执行、重新校验 |
| `manual` | 引擎不自动处理 | 报告补救命令，停止该路径 |
| `informational` | 仅上下文 | 仅在相关时说明，不阻断 |

常见 id 包括 `skill-missing`、`skill-stale`、`skill-scope-unknown`、`skill-user-root-stale`、`control-plane-missing`、`control-plane-drift`、`control-script-broken`、`project-fact-missing`、`workspace-dir-missing`、`fitness-ledger-missing`、`fitness-change-requires-approval`、`openspec-skills-missing`、`python-unusable`、`version-downgrade`、`version-invalid`、`not-installed`。

## 范围选择

Agent 范围显式或推导得出，不做猜测：

1. 显式 `--agent` 优先。
2. 其次使用 `docs/methodology/onboarding.json` 记录的 Agent。
3. 否则只刷新已存在的 Skill 目录；若都不存在，则报告 `skill-scope-unknown` 并询问 Agent，而不是一次性创建六个平台的安装。

安装层级默认取记录中的层级，Tier 1 的安装按 Tier 1 修复。

## 与 onboarding 的关系

完全没有控制面属于**接入**，走 onboarding 流程。修复假设 Harness 已安装但发生漂移，并复用同一套规范动作模型。因此接入、升级、修复与卸载共享同一份「Harness 拥有哪些文件」的定义，而卸载仍是唯一会删除文件的路径。
