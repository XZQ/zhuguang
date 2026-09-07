# 门户构建与状态来源

运行 `uv run python scripts/build_full_delivery_portal.py`，输出 dist/delivery-portal，包含
主页、架构演练、独立答辩页、PPT 及其静态资源、状态逻辑与 status.json。该命令仅构建，
不部署、不上传，也不修改构建脚本。前置 evidence/m4/command-center.html 由
`uv run dianxun command-center` 生成。模板位于 scripts/assets，模型取 config/project-facts.json。

默认 status.json 中所有 Worker 都是 unknown，不根据配置数量推断在线数量。
实际观测可由部署管理员导出为以下格式，然后执行：

```text
uv run python scripts/generate_portal_status.py --observations observations.json
```

```json
{
  "workers": [
    {"name": "sentry", "status": "offline", "observed_at": "2026-09-07T00:00:00Z", "model": null}
  ]
}
```

上例仅说明输入格式，不能作为现场运行证据。五个名称是 orchestrator、sentry、diagnoser、
executor、auditor；status 仅允许 online、offline、unknown。online/offline 必须有原始观测
时间。生成器只输出允许的公开字段，不复制私有日志。持续部署时由可信观测流程周期性生成
该文件，保留原始采样时间。静态门户无法自行证明 Team Room 委派或 Agent 闭环。

页面每 15 秒刷新，3 秒超时；观测超过 120 秒或时间明显在未来则过期。失败、缺失或异常
JSON 显示未知；0 个在线 Worker 保持为 0。模型观测与配置不一致时提示差异。
温度高斯曲线、128 家门店、512 台设备和审批按钮均为浏览器模拟，已在页面注明。

三个文档脚本仍生成对应 Markdown/HTML；PDF 为可选导出，设置 DIANXUN_PDF_BROWSER 为本机
Chromium/Edge/Chrome 可执行文件路径后才生成。显式请求 PDF 时浏览器失败会报错，不能冒充成功。
仓库中历史 PDF 不属于本次网页构建，不用于证明当前版本的运行结果。

验证：`uv run python -m unittest tests.test_delivery_portal -v`，包含 Node 状态逻辑测试和
两次完整构建哈希对比。单元测试使用合成观测，不代表现场 Worker 已在线。
