# 上下文缓存协议

Harness 上下文缓存是仓库侧协议，用于稳定上下文前缀并测量缓存行为；它不替换、不配置宿主 Agent 或供应商缓存。

`context_cache.py fingerprint` 通过 `resolve_context.py` 解析上下文，再按确定的顺序对策略、Profile、根索引和命中的 `AI.md` 原始字节计算 SHA-256。生成的 `prefix_digest` 是 Harness 适配器唯一使用的缓存身份。

适配器每次上下文请求记录 `hit`、`miss` 或 `bypass`。只有 `hit` 和 `miss` 进入命中率分母；宿主无法提供供应商缓存遥测时必须记录 `bypass`，不能冒充命中。

长程任务目标为：

```text
hit_rate = hits / (hits + misses) >= 0.995
```

冷启动算作 miss，不得静默排除。缓存失败属于优化失败，不属于正确性失败；上下文解析仍然 fail-closed。
