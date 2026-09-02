# Changelog

本项目遵循 Keep a Changelog 的结构；当前仍处于开发预览，尚未发布正式生产版本。

## [Unreleased]

### Added

- 线程安全、低基数的 MCP Prometheus 指标与 `/metrics` 端点。
- SQLite 协调控制面确定性恢复演练及可复核 JSON 证据。
- GitHub Actions 门禁：锁定依赖、Ruff、全量测试、评测、消融、指挥台、Seed、恢复演练、Worker 确定性构建和 Python 包构建。
- 贡献、安全、Issue/PR 模板及 SLO/恢复演练运行手册。

### Security

- 指标不使用 tenant、incident、request、trace、actor 或凭据等高基数/敏感标签。
- 继续保持共享 Token 只读、Actor 绑定写权限和目标平台证据边界。

### Fixed

- Skill Registry/provenance 使用显式可移植路径排序，避免 Windows 与 Linux 对大小写排序不同而产生摘要漂移。

## 0.2.0.dev0 - 2026-09-02

### Added

- 有状态冷柜五阶段闭环、6 个 P0 Skill、12 个 P0 MCP 与 3 个默认关闭的知识 MCP。
- AgentTeams `v1.2.3` Worker/YAML、Skill Registry/provenance 和动态证据校验契约。
- tenant/TTL/WAL/乐观版本、lease/heartbeat、唯一超时 successor 与 checkpoint 重启恢复控制面。
- 六场景 M4 评测、单变量消融和只读事故指挥台。

### Fixed

- 收紧审批、角色、幂等、运行时 Schema、证据真实性和商品安全关闭边界。

> 此日期表示仓库开发基线，不代表正式 GitHub Release、云上验收或生产发布。
