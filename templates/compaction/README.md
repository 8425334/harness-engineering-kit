# Token Compaction Preservation Templates

Token 压缩保持机制的可移植模板。让进行中的本轮契约在 auto-compact 后仍可恢复。

## 文件清单

```
compaction/
├── README.md                        # 本文件
├── round-contract.md.template       # 本轮契约文件（≤50 行）
├── save-state.sh.template           # PreCompact 存盘 hook
├── settings-hooks.json.template     # PreCompact + SessionStart 接线片段
├── codex-round-contract.md.template # Codex 本轮契约（手动恢复说明）
└── codex-save-state.sh.template     # Codex 手动存档脚本
```

## 迁移步骤

### 1. 拷贝模板

```bash
mkdir -p .claude/hooks .claude/compaction-state
cp docs/methodology/compaction/round-contract.md .claude/round-contract.md
cp docs/methodology/compaction/save-state.sh .claude/hooks/save-state.sh
chmod +x .claude/hooks/save-state.sh
```

### 2. 合并 hooks 接线

将 `settings-hooks.json.template` 的 `hooks` 片段合并进 `.claude/settings.json`（或 `settings.local.json`）。若文件不存在，直接复制整个 JSON 结构。

### 3. 建立习惯

每轮实施**开始前**更新 `.claude/round-contract.md`（任务/契约字段/文件清单/待办），保持 ≤50 行。压缩后 `SessionStart(matcher=compact)` 会自动把该文件重新注入上下文。

### 4. 验证

```bash
# 手动触发一次 PreCompact（stdin 传入任意 JSON）
echo '{}' | .claude/hooks/save-state.sh
ls .claude/compaction-state/          # 应出现 round-contract-*.md 与 compact-*.json
# 手动恢复（等价于 SessionStart compact 行为）
cat .claude/round-contract.md
```

## Codex 变体

Codex 当前没有项目级 `PreCompact` / `SessionStart` hook，采用显式生命周期：

```bash
mkdir -p .codex/hooks .codex-state
cp docs/methodology/compaction/codex-round-contract.md .codex/round-contract.md
cp docs/methodology/compaction/codex-save-state.sh .codex/hooks/save-state.sh
chmod +x .codex/hooks/save-state.sh

# 长轮次或预计压缩前
bash .codex/hooks/save-state.sh
# 恢复后
cat .codex/round-contract.md
ls -1t .codex-state/round-contract-*.md | head -1 | xargs cat
```

- 环境变量：`${CODEX_PROJECT_DIR:-${CODEX_PROJECT_ROOT}}`
- 状态目录：`.codex-state`（可用 `${CODEX_STATE_DIR}` 覆盖）
- 不要向 `.codex/config.toml` 写入未受支持的 hook 配置键
- 应在根 `AGENTS.md` 声明“轮前读取/更新、压缩前存档、恢复后重读”的习惯
- `.codex/hooks/save-state.sh` 即使不可执行也可通过 `bash` 调用；安装脚本仍会统一设置执行位

详见 `core/harness-engineering.md` 组件 5（英文）与 `i18n/zh/core/harness-engineering.md`（中文）。
