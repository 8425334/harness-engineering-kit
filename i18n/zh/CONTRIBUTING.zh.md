# 贡献指南

感谢你对 AI 辅助开发方法论的贡献兴趣！

## 贡献方式

- **报告问题**：发现 fitness 检查脚本的 bug？模板渲染不正确？提交 issue。
- **提出增强建议**：有新的质量维度想法、更好的 agent 工作流、缺失的模板？提交 feature request。
- **添加示例**：通过贡献到 `examples/` 分享你如何将方法论适配到你的技术栈。
- **改进翻译**：帮助将核心文档翻译成更多语言，放在 `i18n/` 下。
- **修复 bug**：认领一个 open issue 并提交 PR。

## Pull Request 流程

1. Fork 仓库并从 `main` 创建 feature 分支。
2. 进行修改。保持专注 — 一个 PR 只解决一个问题。
3. 如果添加或修改 fitness 检查脚本，请包含测试。
4. 运行 `python3 scripts/onboard.py --plan --json`；已有接入时再运行 `python3 scripts/onboard.py --check` 验证无损坏。
5. 在 `[Unreleased]` 部分更新 `CHANGELOG.md`。
6. 提交 PR，清晰描述改了什么以及为什么。

## 语言策略

- **English** 是 `core/` 文档的权威语言。
- **翻译** 放在 `i18n/<lang>/core/` 下，应与英文源文件保持一致。
- 模板 (`templates/`) 使用 `{{PLACEHOLDER}}` 语法，语言无关。
- Issue 和 PR 的讨论可以使用任何语言，但建议使用英文以提高可搜索性。

## 行为准则

- 保持尊重和建设性。
- 假定善意。
- 关注方法论，而非个人。

## 开发

```bash
# 只读预览接入操作
python3 scripts/onboard.py --plan --json
```

## 许可证

贡献即表示你同意将你的贡献以 MIT 许可证授权。
