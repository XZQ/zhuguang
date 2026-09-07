# 七项审计问题修复记录

基线：`fed0e00241bc39e824de2ce6c06bdd3868020bd1`。每项独立本地提交，不推送。

## 1. 商品安全闭环

Auditor 要求完整批次范围，且 released 批次当前 safe_for_sale 为真；销毁和转移不要求可售。
解禁事务锁定并重查商品事实，关闭前重新聚合。解禁后出现不安全事实时，由 Executor
重新止售，独立核验失败的事件不能关闭。回归覆盖解禁前后同一时钟安全变化、关闭前变化和缺失批次。
没有改变公开 MCP/Skill 契约或数据库结构；回滚代码会重新暴露安全缺口。

## 2. 事件并发和事务

IncidentCase 增加可选 version（旧数据默认为 0），每次写入用数据库条件 UPDATE 比较版本。
冲突抛出 IncidentConflictError，调用方必须重读后重放意图，不能盲目重存旧快照。
新增操作采用 INSERT DO NOTHING，避免同名创建相互覆盖。核验记录和事件聚合在同一连接、
同一事务内提交/回滚；关闭时持有批次锁直到状态提交。

数据库表结构无需迁移，JSON Schema 接受可选 version。升级时停止旧写入实例，避免不支持
CAS 的旧程序并行覆盖。回滚须停写、备份数据库，再在独立事务中移除 case_json 的 version
属性（SQLite json_remove(case_json, '$.version')；PostgreSQL case_json - 'version'），
然后回退程序。不得在新旧程序并行运行时降级数据。
并发测试验证两个旧快照只有一个成功，重读重试后两个事实均保留；失败注入验证无孤立核验记录。

## 3. 安装资源

Docker COPY 包含根 skills/；wheel 打包六个 Skill 的完整文件并在安装模式继续校验摘要。
resource_path 统一解析只读资源；output_path 将安装后的评测/Trace/运行文件写到工作目录，
可由 DIANXUN_OUTPUT_DIR 覆盖。源码模式保留仓库内确定性产物路径。
`python scripts/check_installed_distribution.py --docker-inputs` 按 Docker COPY 清单构造临时
源目录、构建 wheel、安装到仓库外虚拟环境，再以隔离 Python 执行 evaluate 和 demo-run。
本机没有 Docker 引擎；镜像实际构建和容器烟测由第 7 项 CI 门禁执行，不能标为本地已通过。

## 4. Worker 运行时桥接

新增 /runtime MCP 接口，将绑定租户/门店/Worker 的身份、租约、规范 Skill、工具回执和
IncidentService 接通。runtime_contexts 与领域数据原子持久化，重启由数据库恢复；
完整 HTTP 测试覆盖闭环、partial、租约、越权和 checkpoint 提交失败回滚。
部署配置已接线，Worker 包保持字节不变，新增规则由 YAML 传递。
接口、凭证配置、迁移和回滚见 [运行接口说明](../operations/worker-runtime.md)。

## 5. HTTP 与就绪检查

HTTP 默认最多处理 32 个连接，每个连接 10 秒绝对截止时间，覆盖慢速头部和请求体；
超过容量返回 503，超过 1 MiB 的 Content-Length 在读取 body 前返回 413。
拒绝重复长度头和 Transfer-Encoding，避免歧义。PostgreSQL 连接、语句和锁等待各有 5 秒上限。
`/live` 仅报告进程存活；`/ready` 和兼容 `/health` 检查必要业务表、初始化状态、Skill 摘要。
数据库或 Schema 不可用返回 503；Kubernetes 和 Docker 探针已区分配置。
回归使用真实慢速 socket、超限请求、连接耗尽和数据库故障验证。

## 6. 门户与证据口径

移出嵌入脚本的 HTML/Markdown/SVG 到可维护模板；门户和答辩页共享同一内容源。
移除作者机器路径和构建脚本改写源码，新增完整门户构建入口与公开状态生成器。
Worker 状态区分未知、离线、过期和 0 个在线；模型信息取事实配置并检测观测差异。
高斯曲线/审批按钮标明模拟，evaluate 更正为六场景评测，未验证部署声明已更正。
两次完整构建哈希一致，Node 状态逻辑与不泄漏额外观测字段的测试通过。
详见 [门户构建说明](../operations/delivery-portal.md)。

## 7. 质量门禁与文档证据一致性

Ruff 规则保持原样，全仓 lint/format 通过。CI 增加 Ubuntu/Python 3.11 与 Windows/Python
3.12 矩阵、Node 22、隔离 wheel 入口、门户和文档重建、事实发现数核对，以及独立 Docker
构建/非 root/readiness/认证/MCP Trace/Worker runtime 烟测。容器默认输出与 Trace 指向
可写的 /var/lib/dianxun，避免带 Trace 的工具调用写入只读 /app；Docker build context 排除
虚拟环境、Git、运行数据库与本地凭证文件。Docker 脚本的 HTTP 验证逻辑已对本地真实服务运行。

2026-09-07 在 Windows / Python 3.12.13 完整回归：105 项发现、103 通过、2 条 PolarDB
集成跳过（缺少隔离 DSN 和 reset opt-in），0 个失败。六场景评测 6/6，Top-1/Top-3 6/6，
Evidence 45/45、阶段 Trace 26/26，五类安全违规均为 0；四变体消融门禁通过。Seed 与恢复
演练 --check 通过，wheel/sdist 构建、仓库外安装资源与 evaluate/demo-run 烟测通过。
Worker ZIP 重建后仍为 35 文件/6 Skills，SHA-256 保持既有固定值。

事实 JSON、README、部署说明、当前比赛材料与 HTML PPT 同步本地测试口径；带日期历史
记录保留原值。清理把模拟动画、配置或未经验证环境写成真实运行的旧声明。三个 Markdown
手册与 SVG 从模板生成；门户包含所有必需入口和 unknown 状态源。
评测、消融、指挥台、Worker 包、手册与完整门户再次重建后，23 个输出文件 SHA-256 全部一致。

限制：本机没有 Docker，新增容器 job 和 Windows/Linux GitHub CI 因未 push 尚未执行；
安装烟测不能替代它们。真实 AgentTeams 身份注入、Team Room、PolarDB、OSS 和门店运行
仍待外部验收。浏览器远程调试未获开启，本次只有 Node 与构建检查，没有视觉烟测；既有
PDF 没有重建，不作为当前版本证据。运行接口会阻断失败阶段并允许外部事实修复后重试，
尚未自动调度新的诊断循环。

本地验证不代表 AgentTeams、PolarDB 或门店生产环境已经验收。
