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

## 后续项

## 3. 安装资源

Docker COPY 包含根 skills/；wheel 打包六个 Skill 的完整文件并在安装模式继续校验摘要。
resource_path 统一解析只读资源；output_path 将安装后的评测/Trace/运行文件写到工作目录，
可由 DIANXUN_OUTPUT_DIR 覆盖。源码模式保留仓库内确定性产物路径。
`python scripts/check_installed_distribution.py --docker-inputs` 按 Docker COPY 清单构造临时
源目录、构建 wheel、安装到仓库外虚拟环境，再以隔离 Python 执行 evaluate 和 demo-run。
本机没有 Docker 引擎；镜像实际构建和容器烟测由第 7 项 CI 门禁执行，不能标为本地已通过。

## 后续项

4. Worker 运行时协调和领域桥接。
5. HTTP 请求边界与就绪探测。
6. 门户真实状态与可复现构建。
7. 质量门禁与文档证据一致性。

本地验证不代表 AgentTeams、PolarDB 或门店生产环境已经验收。
