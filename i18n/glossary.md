# Terminology Glossary / 术语表

| English | 中文 | Meaning |
|---|---|---|
| Harness Engineering | Harness 工程 | Repository-native authority, context, workflow, gates, and evidence system |
| Engineering Skill | Engineering 技能 | The single task orchestrator for backend, frontend, and fullstack code changes |
| Root adapter | 根适配入口 | Short native `AGENTS.md` or `CLAUDE.md` file that establishes authority and routing |
| Agent policy | Agent 策略 | Canonical project commands, paths, permissions, and delivery references |
| Context index | 上下文索引 | Root `ai.json`: compact machine-readable project map and routes to every maintained `AI.md` |
| Context detail | 上下文详情 | Indexed `AI.md`: human- and machine-readable local responsibilities, boundaries, navigation, and verification |
| Context impact | 上下文影响 | Approval-bound decision stating whether changed code requires `ai.json` or `AI.md` maintenance |
| SDD | 规格驱动交付 | Contract production through proposal, behavior spec, design, tasks, and approval |
| RAM | 读-分析-建模 | Backend design work performed during Explore and Propose |
| RAD | 读-分析-分解 | Frontend design work performed during Explore and Propose |
| Apply | 实施 | Implementation that consumes an approved contract and permits only scoped drift checks |
| Fitness gate | 质量门禁 | Deterministic project check that produces verification evidence |
| Availability contract | 可用性契约 | Harness `manifest.yaml` plus exact Skill resources and installed digests |
| Runtime selection | 运行时选择 | Observed `skill.triggered` or `skill.fallback` event, distinct from file installation |
| Production record | 生产记录 | Linked observability, rollout, rollback, approval, and audit state for production delivery |
| Operational done | 运营完成 | Deployment has completed observation or rollback closure, beyond technical verification |
| Self-Refine | 自反馈迭代 | Bounded Generate → Self-Critique → Refine → Re-check loop inside a lifecycle phase |
| Self-Critique | 自我批判 | Structured inspection that names concrete findings against requirements and risk criteria |
| Requirement Reflection | 需求反思 | Response-level check that pauses consequential work when intent, evidence, authorization, or constraints are unclear or inconsistent |
| Reflexion | 反思记忆 | Advisory lessons retained across tasks; never an automatic authority or approval source |
| Lesson memory | 项目经验记忆 | Reviewed, scoped prevention guidance retrieved during Explore and verified by normal gates |
