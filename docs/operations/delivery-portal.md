# 门户构建与状态来源

运行命令从仓库根目录执行。构建只产生本地制品，不代表线上展示站同步更新。

~~~bash
uv run dianxun command-center
uv run python scripts/build_animated_svg.py
uv run python scripts/build_full_delivery_portal.py
~~~

输出 dist/delivery-portal，包含主页、模拟架构演练、独立答辩页、PPT 与静态资源、状态逻辑和 status.json。首次门禁与维护要求见[CONTRIBUTING](../../CONTRIBUTING.md)。

## 模板与输出

| 源 | 生成器 | 输出 |
|---|---|---|
| scripts/assets/delivery_portal_html_content.html | scripts/build_delivery_portal.py | index.html |
| scripts/assets/native_defense_web_dossier_html.html 与 native_defense_web_standalone_html.html | scripts/build_native_defense_web.py；主页也使用 dossier | defense.html 及主页答辩区 |
| scripts/assets/combined_animation_html_content.html | scripts/build_combined_animation.py | architecture-flow.html（浏览器模拟） |
| scripts/assets/animated_svg_svg_content.svg | scripts/build_animated_svg.py | docs/assets/architecture-flow.svg |
| ppt/ | scripts/build_full_delivery_portal.py | ppt/ 原样复制；当前准备入口为 ppt/finals.html |
| docs/competition/ 三份复赛 PDF | scripts/build_full_delivery_portal.py | 原文件名复制到输出根目录，保留历史版本字节 |
| config/project-facts.json 与公开观测 | scripts/generate_portal_status.py | status.json；配置模型和观测模型分别展示 |

旧三套复赛手册的 Markdown 已归档，三个生成器和六个重复模板已停用。完整门户构建会清理输出目录中已退役的 defense-guide.html、defense-guide-illustrated.html、defense-master.html；三份 PDF 保留在 docs/competition 原路径，并原样复制到输出目录，不删除、不重新导出。

[复赛归档](../archive/2026-09-semifinals/README.md)保留历史勘误并链接 PDF 原文件。当前构建不导出 PDF；三份复赛 PDF 与 ppt/ 内的既有 PDF 只作为对应日期的制品复制。需要新 PDF 时须从选定的当前源显式导出并逐页检查，不能由网页构建成功推断 PDF 已更新。

## 状态观测

默认所有 Worker 为 unknown，不从配置数量推断在线数量。管理员可导出公开观测，再执行：

~~~text
uv run python scripts/generate_portal_status.py --observations observations.json
~~~

~~~json
{"workers":[{"name":"sentry","status":"offline","observed_at":"2026-09-07T00:00:00Z","model":null}]}
~~~

该数据只说明格式。名称为 orchestrator、sentry、diagnoser、executor、auditor；状态仅 online/offline/unknown。online/offline 必须有原始观测时间；生成器过滤私有字段。

页面每 15 秒刷新，3 秒超时；超过 120 秒或明显未来的观测视为过期。错误、缺失或异常 JSON 显示未知，0 个在线保持 0；模型观测与配置不一致时提示。模拟曲线、128 店/512 设备和审批交互都不是传感器或人员证据，页面正文也必须保持这一口径。

## 验证与交付

~~~bash
uv run python -m unittest tests.test_delivery_portal -v
~~~

现有回归检查 Node 状态逻辑、两次构建哈希、源码不被改写和退役输出清理。决赛文案入口是[讲稿](../competition/finals/03-决赛逐页讲稿与问答.md)；历史门户链接和准备包的版本单独保留，不将本地构建当线上发布。
