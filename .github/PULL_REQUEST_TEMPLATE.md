## 变更目的

<!-- 说明问题与范围。 -->

## 实现与风险

<!-- 说明关键实现、兼容性、安全边界和回滚方式。 -->

## 验证

- [ ] `uv run ruff check .`
- [ ] `uv run ruff format --check .`
- [ ] `uv run python -W error::ResourceWarning -m unittest discover -v`
- [ ] 受影响的评测/生成物已重建且 `git diff --exit-code` 符合预期
- [ ] 暂存差异不含 Token、真实身份、业务隐私或未脱敏 Trace

## 证据边界

- [ ] 没有把本地 Mock、静态契约或确定性测试写成云上/生产实测
- [ ] 若涉及 AgentTeams、PolarDB、OSS 或 HITL，已明确仓库内证据与外部待验证项
