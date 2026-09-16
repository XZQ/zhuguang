# 决赛服务端部署与取证手册

维护日期：2026-09-15。供队友拉取代码后执行；任务状态只维护在[统一待办](../待办.md)的 F01–F08。
本轮没有可用的 AgentTeams／Element、PolarDB 或授权门店环境，因此本手册中的外部步骤是操作与验收要求，不是已经运行成功的报告。

## 1. 固定代码与本地门禁

在 Linux 测试服务器使用 Python 3.11+、uv、Node.js 22+。先检查工作区；有本地修改时先保存，不能用 reset 覆盖。

```bash
git status --short --branch
git pull --ff-only origin main
git rev-parse HEAD
uv sync --locked --group dev --extra postgres
uv run ruff check .
uv run ruff format --check .
uv run python -W error::ResourceWarning -m unittest discover -v
uv run python scripts/check_quality_facts.py
```

完整门禁见 [CONTRIBUTING](../../CONTRIBUTING.md)。记录实际 SHA、Python／PostgreSQL／AT 版本和命令退出码。文档内的测试数字是本地记录，队友必须保存目标环境的新结果。

本轮没有数据库结构迁移，也不改变 Worker ZIP 的 Python 实现来源。运行时新增了证据门禁：旧记录缺少适用凭证时不能按成功关闭；应补证并由 Auditor 再验，不回填虚构回执。回滚应先保持停售、暂停新任务，再切回已留存的镜像摘要；不要为了恢复旧的宽松验收而解除限制。

## 2. 身份、数据库与镜像

先由管理员建立独立、可重置且名称包含 `test` 的数据库，以及独立迁移／运行／业务只读登录。测试会重置测试库数据并应用安全角色，禁止指向已有业务库。

秘密由服务器秘密管理器或仓库外权限受限文件注入，不写进命令参数、YAML、聊天、Trace 或录屏。需要的配置：

| 用途 | 配置 |
|---|---|
| 迁移 | `DIANXUN_DATABASE_URL` 指向管理员 DSN；完成后从该进程退出 |
| 条件集成测试 | `DIANXUN_TEST_POSTGRES_DSN`、`DIANXUN_TEST_POSTGRES_READONLY_DSN`、`DIANXUN_ALLOW_TEST_DATABASE_RESET=1` |
| 正式运行 | `dianxun-polardb-runtime/database-url` 为受限运行 DSN |
| Worker 身份 | `dianxun-agent-identities/runtime-tokens-json`；每个 Worker 独立 actor、worker_id、tenant_id、store_id |
| 人工审批与证据 | `actor-tokens-json` 中独立 Human 身份，禁止提供给 Worker／模型 |
| 可选知识检索 | `dianxun-embedding-runtime` 的 endpoint、model、api-key，仅 RAG overlay 使用 |

按 [AgentTeams 部署说明](../../agentteams/README.md)创建角色及 principal scope，迁移顺序：

```bash
uv run dianxun db-bootstrap --profile core --profile security
```

core 仍需要目标实例支持 `vector` 扩展。`pg_cron` 需要实例侧预加载、权限与执行数据库配置；确认这些条件后再应用 `cron`，foreign table 配置和权限确认后应用 `archive`。不要把扩展不支持改成忽略错误。

```bash
uv run dianxun db-bootstrap --profile cron --profile archive
uv run python -m unittest -v tests.test_polardb_integration
```

该测试类仍是 2 项条件测试。第一项增加了真实月首日／越维护窗口拒绝、SAVEPOINT 后继续事务、分区创建，以及知识审核后的 PostgreSQL vector 写入和检索。向量测试使用本地 hash embedding，仅证明数据库调用链，不证明语义模型效果。第二项验证独立只读登录和总部／门店边界。**必须报告 2 passed、0 skipped**；还要另测运行账号的跨租户、跨门店隔离和允许写入路径，管理员测试通过不能替代运行账号验收。

构建并将镜像上传到集群可访问的 Registry，使用实际 SHA 标签和镜像摘要。以下构建不会自动推送镜像：

```bash
BUILD_SHA=$(git rev-parse HEAD)
docker build --build-arg DIANXUN_BUILD_SHA="$BUILD_SHA" \
  -f packages/dianxun-mcp/Dockerfile -t dianxun-mcp:"$BUILD_SHA" .
python scripts/check_docker_image.py --image dianxun-mcp:"$BUILD_SHA"
```

主链部署使用 `agentteams/overlays/polardb`，默认关闭 P1／RAG，不需要 embedding Secret。需演示知识检索时才使用 `agentteams/overlays/polardb-rag`。

两套 overlay 均通过 kubectl v1.34.1 的默认 Kustomize 渲染检查，使用 `agentteams/mcp` 作为 base；已核对 Deployment、Service、PVC、运行身份及 P1／RAG 开关。此结果只证明本地清单可渲染，集群权限、存储、镜像拉取和服务运行仍需以下步骤验收。

```bash
kubectl apply -f agentteams/namespace.yaml
# 先按部署说明创建 Secret、确认 PVC 与镜像名称／摘要。
kubectl kustomize agentteams/overlays/polardb > /tmp/dianxun-polardb-rendered.yaml
# 在这份渲染文件中将本地镜像名替换为已上传的实际镜像摘要，再 apply。
kubectl apply -f /tmp/dianxun-polardb-rendered.yaml
kubectl -n dianxun rollout status deployment/dianxun-mcp
kubectl -n dianxun get pods,pvc,service
```

`/live` 证明进程存活；`/ready` 检查必要状态和契约。响应新增 `build_revision`，未注入有效 40 位小写 SHA 时为 `unknown`；还需与 Pod imageID、实际镜像摘要对照，它不是独立的来源认证。就绪探针不能证明 AT 委派、外部设备接口或商品处置完成。

## 3. 同一门店事件的真实 AT 演示

按照 [运行与恢复](runtime-recovery.md)配置真实 Worker 身份和阶段工具，使用隔离门店 `demo/S03`。ScenarioEngine 的 reset 会初始化测试状态；共享运行库有任务时禁止重置。服务端已提供已应用场景事件→运行事件→Worker assignment 的入口，目标 AT 的 Manager 委派、真实房间消息与身份注入仍须实机接通，不能把内部 assignment 当作平台已创建的 task。

### 3.1 场景进入 Worker 协议

仅在全新隔离演示库启用 `DIANXUN_SCENARIO_BRIDGE_ENABLED=1`；固定历史时间的模拟读数还需 `DIANXUN_SCENARIO_VIRTUAL_CLOCK=1`。第二个开关只作用于通过场景入口创建的事件，租约和超时仍使用真实时钟，普通 runtime_open 事件仍检查真实证据时效。生产配置不要开启这两个演示开关。

先停止该演示的服务写入，在全新本地隔离库应用 A 的零分钟事件：

```bash
uv run dianxun scenario-reset demo/state/scenarios/coldchain-compressor-failure.json \
  --db /secure/demo-test/runtime.db
```

PolarDB 的初始化由管理员在已授权的独立测试库完成；使用仓库外 DSN 环境配置和 Python 的 create_state_store／ScenarioEngine.reset，避免把 DSN 作为进程参数。必须先确认数据库名、清空范围和无其他任务，不能对共享运行库 reset。启动 MCP 时指向同一状态库。

Orchestrator 从 `/runtime` 调用以下工具参数：

```json
{"name":"runtime_ingest_scenario","arguments":{"scenario_id":"coldchain-compressor-failure","event_id":"001-device-fault"}}
```

工具仅接受安装目录中的场景、匹配初始化摘要且已应用的设备事件；由 Token 判断租户与门店，稳定派生 incident_id，同一事件重送返回已有结果。source_events 保存场景/事件摘要、输入和虚拟时间，不会把 ground_truth 根因送给 Worker。后续沿用 runtime_poll、runtime_assign、runtime_complete。记录返回的 incident_id；场景中后续审批和回执使用固定 Demo action_id，不能直接推进整份旧脚本冒充新任务的人工执行，必须按当前 runtime 的动作编号提交独立 Human 证据。

### 3.2 绑定 AT／Element 原始记录

Sentry、Diagnoser、Executor、Auditor 用自己的 assignment 调用 `runtime_link_platform`，参数包含 incident_id、assignment_id、最新 expected_version、project_id、task_id、room_id、message_id、原始脱敏导出文件的 evidence_sha256。`link_kind=assignment` 仅允许当前有效租约；同一 room/message 的原样重送幂等，修改绑定被拒。

runtime_complete 返回 output、output_digest 和 context_version。失败/partial 也保存本次输出并推进版本，重试必须更新 expected_version。Worker 将自己的结果发布到平台后，以 `link_kind=result` 和该 output_digest 关联结果消息；结果关联允许已完成任务，但摘要必须匹配服务端保存的该 Worker 输出。Executor 和 Auditor 各自提交，不能互相代报。历史失败输出保留在 context.attempt_outputs，重做不会覆盖。

消息 ID 和文件摘要属于 Worker 提交的关联元数据，状态始终是 worker_submitted_not_platform_verified；代码没有代替平台校验 sender、消息正文或文件真实性。队友需将原始导出与上述字段逐条对照，再形成最终验收报告。

准备成功、失败两轮运行，各有独立 incident_id／trace_id；现行 AT 证据 schema 还要求两轮独立 project_id。业务门店相同，运行对象不能混用。人工确认必须来自独立 Human 入口，ScenarioEngine 自动审批只能标记为模拟。

需要连续保存：

1. 原始模拟事件编号、读数、受影响批次；虚拟时间与真实执行时间分别显示。
2. Manager→Orchestrator→各 Worker 的真实 AT task、Element room/message id。
3. 每次任务的 assignment_id、阶段、租约、Skill 版本／digest、request_id、trace_id。
4. Executor 的处置结果与 Auditor 自己重新查询的结果；两者身份不同。
5. 独立 Human 批准、实物凭证、最终数据库状态，以及失败后的原轮次和新轮次记录。

成功案例用 A；失败案例以 E 为起点，设备恢复但商品证据不足，保持销售限制。E 固定合成场景停在等待人工处置，不是已经实跑的 AT 驳回重做录像。真实驳回后补证／重派到终态，以及中断恢复、重复请求无额外副作用，需在服务器另跑。

```bash
uv run python scripts/verify_agentteams_evidence.py /secure/evidence/agentteams-run.json \
  --output /secure/evidence/agentteams-validation.json
```

校验器不从平台获取消息，也不验证 evidence_ref 指向的文件真实性。必须另保存对应的脱敏原始导出、文件哈希和可访问链接，不能手填一份 JSON 代替真实协作。

## 4. 商品证据契约

`record_manual_evidence` 仍只允许 Human／ScenarioEngine；Worker 不能自造人工证据。新增条件使用现有 metadata 和 actions 表，不新增数据库列。

人工测温必须关联当前 incident、batch_id、device_id，包含有限数值 temp_c、instrument_id、measurement_point=`product`、calibrated_at、calibration_valid_until；时间均须含时区。观测不晚于评估时刻且不超过 5 分钟，校准覆盖观测和评估时刻。柜内空气测温、错批次或过期仪器不能替代当前商品测量。设备序列按真实时间归一并去重；同时间冲突、单样本、超过 30 分钟缺测、最新样本超过 5 分钟、未来／无效记录均不能形成放行依据。该 30 分钟门禁适配合成样本，真实采样周期和商品策略仍须负责人批准；它不证明历史暴露覆盖完整。

转移／报损仍可先记录执行状态；只有具备 `evidence_type=disposition_receipt` 的独立凭证才能通过商品核验。凭证必须：

- 关联该 incident 的当前处置 action_id、batch_id、disposition；动作已 completed、类型正确且更新时间匹配批次。
- observed_at 不早于处置、不晚于当前时间，quantity 大于零且等于当前整批数量；部分接收保持未完成。
- source_location 匹配设备，receipt_ref 非空，executor_id 与 confirmed_by 非空且不同。
- 转移：destination_location 不同于源位置，received=true，destination_temp_c 符合该商品上下限。
- 报损：destroyed=true、disposal_method 非空。仅批准报损不能声称销毁完成。

字段校验不能证明实际拍摄、现场身份或物理真伪。可信接收系统／人员、批次范围版本、拆批、POS 和多渠道对账继续按 T02／T05 验收。新轮次必须提交对应新动作回执，旧回执不能复用。

## 5. 本地封存与离线回放

下面两条 capture 各自启动全新的临时合成运行，不连接现有运行库；输出目录必须不存在。SQLite 使用 backup API 封存提交状态，包含 WAL 中已提交页面。成功后留下的 bundle 不随临时目录删除。

```bash
uv run python scripts/capture_replay.py --case success --output tmp/finals-case-a
uv run python scripts/capture_replay.py --case failure --output tmp/finals-case-e
uv run --no-sync python scripts/replay.py tmp/finals-case-a
uv run --no-sync python scripts/replay.py tmp/finals-case-e --html tmp/finals-case-e/replay.html
```

包内包含 state.sqlite、trace.sqlite、逐条 audit.jsonl／trace.jsonl、result.json、scenario.json、policy.json、manifest.json 和 replay.html。回放器不调用模型、不执行动作，以只读 SQLite 校验哈希、数据库完整性、终态与逐条导出一致性。HTML 可断网打开，展开每条记录查看。哈希是完整性检查，不是外部真实性认证；生成时工作区有修改会在 provenance 标记 dirty_worktree=true，正式取证应在干净固定版本重新生成。

运行 DB 和原始 Trace 不进入 Git。需要交付时将审阅后的证据包存放到权限受控制品区，并在验收记录填位置和哈希。现有运行库使用下面的版本 2 格式；旧 synthetic_local_run 包仍按原格式验证。不能修改 source_kind 把合成包升级为平台证据。

### 5.1 封存已有运行库（SQLite／PostgreSQL）

`scripts/capture_runtime.py` 只读取已有数据库，不初始化、不迁移、不运行场景。先暂停本次演示的 Worker、外部写入和恢复调度，再使用 `--quiesced` 声明确已暂停。程序对比采集前后可见状态和 Trace，发生变化即拒绝封存；该检查不能证明所有未观测写入都已停止。输出目录须不存在。

```bash
uv run python scripts/capture_runtime.py \
  --state /secure/demo-test/runtime.db --trace-db /secure/demo-test/trace.db \
  --tenant demo --store S03 --incident INCIDENT_ID \
  --output /secure/evidence/runtime-sqlite-run --quiesced

# DIANXUN_CAPTURE_DSN 由秘密管理器注入；不在参数中展开 DSN。
uv run --extra postgres python scripts/capture_runtime.py \
  --database-env DIANXUN_CAPTURE_DSN --trace-db /secure/demo-test/trace.db \
  --tenant demo --store S03 --incident INCIDENT_ID \
  --output /secure/evidence/runtime-pg-run --quiesced --allow-isolated-dump
```

PostgreSQL 需要与服务器兼容的 pg_dump，可通过 `--pg-dump` 指定安装路径。只允许实际连接的数据库名包含 test 的专用隔离库，并要求显式全库导出 opt-in。迁移管理员/备份登录需具备读取整个测试库的权限；scope 只限定事件档案，pg_dump 和 SQLite 快照均包含整个源库。不可将共享多租户库仅改名后用于演示封存。

PostgreSQL 事件记录和 pg_dump 共用 REPEATABLE READ、READ ONLY 事务导出的 snapshot；连接参数经子进程环境传递，原始错误诊断不打印。SQLite 使用当前读事务的 backup API。包内为数据库快照、casefile.json、audit.jsonl、trace.jsonl、manifest.json、replay.html。Trace 与业务库分开存储，不宣称跨库原子快照。

```bash
uv run --no-sync python scripts/replay.py /secure/evidence/runtime-pg-run \
  --html /secure/evidence/runtime-pg-run/replay.html
```

离线校验检查哈希、事件/Trace 关联及逐条导出；SQLite 还与快照表内容核对。pg_dump 二进制在离线校验中仅验完整性，不等于已经成功恢复。来源固定为 runtime_database_capture，平台和物理真实性均需另验。

### 5.2 恢复后的数据对账

由 DBA 将 state.pgdump 恢复到另一个空的隔离测试库，使用对应 PostgreSQL 扩展与角色。pg_dump 不包含集群角色，需先在隔离目标预建源库策略引用的角色；不要在原库执行 restore。使用受控 PG 环境配置运行 `pg_restore --no-owner --no-acl --exit-on-error --single-transaction --dbname=RESTORE_TEST_DB /secure/evidence/runtime-pg-run/state.pgdump`，保存真实退出码和脱敏日志。目标失败时不得继续宣称已恢复。

将目标 DSN 通过 DIANXUN_RESTORED_DSN 注入，然后执行只读对账：

```bash
uv run --extra postgres python scripts/capture_runtime.py \
  --database-env DIANXUN_RESTORED_DSN --trace-db /secure/demo-test/trace.db \
  --tenant demo --store S03 --check-restored /secure/evidence/runtime-pg-run
```

工具拒绝使用同一源库标识进行恢复对账，比较事件、上下文、设备、商品、审批、动作、回执、核验及审计内容；这是该事件的数据一致性检查，不代替全库恢复、托管切换或 RPO/RTO 验收。本地 SQLite 可以把 state.sqlite 复制到另一路径，用 `--state` 代替 `--database-env` 检查，已完成此本地回归。

### 5.3 在线追溯页

服务端 `/operations` 提供只读页面。使用受控网络的 HTTPS 入口或本机端口转发访问，输入独立 Human 或 Worker 运行身份；Token 仅留在页面内存，退出会清空事件内容。页面通过 `/runtime` 的 runtime_cases（游标分页）和 runtime_casefile 查询，租户/门店取自 Token，跨范围请求被拒，数据库连接本身为只读快照。

页面分别展示设备、商品、销售限制、Worker 接单与租约、独立核验、平台消息关联、每次输出、恢复历史、审批/实物凭证、逐条审计和 Trace。当前规则/注册表与历史审计/Span 版本分别显示；来源、构建 SHA、业务时间和证据时钟明确列出。各类查询最多显示 1000 条，超限明确提示截断；封存上限为每类 100000 条，超限拒绝，不导出缺失内容。设备接口是否真实在线和平台状态仍以目标系统观测为准。

## 6. 分区、cron、归档与 P0001

条件集成测试覆盖两条 partition guard。应用将 SQLSTATE=P0001 转为 AUDIT_MONTH_INVALID、AUDIT_WINDOW_REJECTED 或 DATABASE_POLICY_REJECTED，回滚业务写入和幂等记录，不返回数据库原始诊断。响应 audit_ref 为空时表示未成功写审计，不能记作已审计；由运维渠道记录失败并修复输入／维护配置，不盲目重试。

在隔离实例执行正常分区创建、再次创建的幂等检查，并保存 `pg_inherits` 中实际分区。要证明 cron 运行，须在隔离库临时安排短周期的同等作业，等它实际触发，再取消临时作业；仅手工调用函数或查询 cron.job 不够。保存 cron.job_run_details 与 dianxun_cron_health 的 runid、状态和开始／结束时间。夜间复盘当前仅入队，不等于 AgentTeams 复盘已执行。

归档须由管理员先配置独立 foreign table。使用隔离月分区的小规模合成审计数据调用 `stage_audit_partition_to_foreign`，重复调用并核对源／目标条数、内容摘要与 manifest。再注入目标缺行、等量内容篡改并确认验证拒绝。函数已在首次复制和重跑时使用完整行 JSONB 的 `EXCEPT ALL` 核对内容与重复数量；旧 manifest 不得用于另一个目标表。函数不删除源分区。内容核对证明当前读取快照的一致性，不保证归档目标之后不被修改，也不能代替 OSS 持久性与灾备验证。

2026-09-16 已在首尔独立、无网络的 PostgreSQL 16/pgvector 容器中实跑 `postgres_fdw` 合成归档回归：首次复制、重复调用、等量篡改拒绝、目标替换拒绝、缺行拒绝、首次复制内容变化后的回滚。源码为 `tests/sql/archive_regression.sql`，CI 的 `postgres-archive` job 从全新数据库应用 core/security/archive 后执行它。测试脚本只允许专用 `zhuguang_archive_test` 数据库，并会清空其中合成审计和归档夹具；严禁用于业务库。此结果不是 PolarDB、OSS、cron 或真实门店验收，F04 其余条件继续保留。

## 7. 托管切换与业务量化

F05 必须另取得具体隔离实例和故障注入授权。用唯一序号和幂等键连续写入测试事件，在客户端独立保留已收到成功响应的记录与单调时钟。按服务商支持的操作发起切换，保存控制面事件；随后重连、对账、恢复 Worker，验证批准、停售、回执、审计和 checkpoint 没有不一致，也没有重复副作用。

RPO 报告已确认成功但恢复后缺失的记录数及时间范围；RTO 从故障开始到业务读写、对账和任务恢复满足条件，不能只计 Pod Running 或数据库可连接。未取得成功响应的请求另列未知结果并对账。保存原始样本、故障起止、负载和版本。单次切换不会同时证明 OSS 灾备、跨地域恢复或生产 SLO。

F06 使用授权脱敏案例做知识审核→向量检索→诊断引用，记录模型、维度、查询、Top-K、引用依据及人工评估；hash 向量测试不作语义收益宣传。F07 在同权限／安全门的人工、规则、Agent 流程下比较发现至遏制时间、总处置耗时、人工主动操作时间、复核补证次数和失败率；虚拟时钟不是实际耗时，没有真实基线不填写改善百分比。

每项验收记录采用：`任务 ID / 代码 SHA / 镜像摘要 / 环境与数据性质 / 输入或故障 / 命令及退出码 / 预期与实际 / 原始证据位置与 SHA-256 / 遗留限制 / 执行人与复核人`。正式讲稿、PPT、PDF、录屏按最终验收版本冻结，见 F08。
