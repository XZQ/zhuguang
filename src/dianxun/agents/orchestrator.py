"""改造前 5 个业务 Agent 的顺序编排基线。

Framework Manager 不计入业务 Agent。当前实现仍使用 TaskContext 与八个
运行步骤；M2 将迁移为五阶段业务模型和每个异常一个 IncidentCase。

对应赛题 1.1/1.3:多 Agent 协同,完成 8 步闭环
  任务输入 → 任务拆解 → 上下文传递 → 工具调用 → 结果验证 →
  执行证据沉淀 → 审批与回滚 → 经验沉淀

5 个 Agent(身份见 06-Agent-Identity清单.md):
  Orchestrator 总控/Team Leader:任务拆解、调度、状态追踪、冲突仲裁
  Sentry        巡检:多源聚合、异常识别、降噪定级
  Diagnoser     诊断:跨店对标、维度下钻、根因定位
  Executor      处置:方案生成、执行、审批触发、回滚
  Auditor       稽核:恢复验证、效果评估、复盘沉淀

闭环状态机(ContextBus.TaskContext.state):
  created → detecting → diagnosing → approving → executing → verifying → reviewing → closed
  (验证失败 → reopened → diagnosing)
"""

from __future__ import annotations
from typing import Any

from .. import trace
from ..context_bus import ContextBus, TaskContext
from .. import skills
from .. import mcp


class Orchestrator:
    """总控 Agent / Team Leader。

    职责:接收任务 → 拆解子任务 DAG → 调度各 Worker Agent → 追踪状态机。
    遵循 AgentTeams delegation-first:只调度,不亲自执行领域任务。
    """

    def __init__(self) -> None:
        self.bus = ContextBus()
        self.sentry = SentryAgent()
        self.diagnoser = DiagnoserAgent()
        self.executor = ExecutorAgent()
        self.auditor = AuditorAgent()

    # ===== Team Leader:任务拆解与调度 =====
    def run_task(self, task_id: str, scope: dict, trigger: str = "scheduled") -> dict:
        """执行一个完整闭环任务。返回复盘报告。"""
        tid = trace.new_trace_id()
        ctx = self.bus.create(task_id, tid, trigger=trigger, scope=scope)
        print(f"\n{'='*64}\n🚀 任务 {task_id} 启动 | trace={tid} | 范围={scope}")
        try:
            with trace.span("orchestrate", "agent", tid, input={"task_id": task_id, "scope": scope}) as sp:
                # 1. 任务拆解(总控) → 派给巡检
                ctx.transition("detecting", "Orchestrator", "派发巡检任务")
                self.sentry.detect(ctx)
                # 无异常 → 直接收口
                if not ctx.anomalies:
                    ctx.transition("closed", "Orchestrator", "无异常,闭环")
                    print(f"✓ 任务 {task_id} 无异常,闭环")
                    sp.output = {"result": "no_anomaly"}
                    return {"task_id": task_id, "result": "no_anomaly", "trace_id": tid}

                # 2. 逐个异常走诊断 → 处置 → 验证(全部处理完后再统一复盘)
                for anom in ctx.anomalies:
                    ctx.transition("diagnosing", "Orchestrator", f"派发诊断:{anom['type']}@{anom['store_id']}")
                    self.diagnoser.diagnose(anom, ctx)

                    ctx.transition("approving", "Orchestrator", "进入审批/处置")
                    self.executor.handle(anom, ctx)
                    ctx.transition("executing", "Executor", "处置已执行")

                    ctx.transition("verifying", "Orchestrator", "派发验证")
                    ok = self.auditor.verify(anom, ctx)
                    if not ok:
                        ctx.transition("reopened", "Auditor", "验证失败,回诊断")
                        ctx.transition("diagnosing", "Orchestrator", "二次诊断")
                        self.diagnoser.diagnose(anom, ctx, retry=True)
                        ctx.transition("approving", "Orchestrator", "二次处置")
                        self.executor.handle(anom, ctx)
                        ctx.transition("executing", "Executor", "二次处置已执行")
                        ctx.transition("verifying", "Orchestrator", "二次验证")
                        self.auditor.verify(anom, ctx)
                    # 循环继续:下一轮 transition("diagnosing") 合法(verifying→diagnosing)

                # 3. 全部异常处理完,统一复盘沉淀
                ctx.transition("reviewing", "Orchestrator", "全部异常处置完成,派发复盘")
                report = self.auditor.review(ctx)
                ctx.transition("closed", "Orchestrator", "闭环完成")
                sp.output = {"result": "closed", "anomalies": len(ctx.anomalies)}
                print(f"✓ 任务 {task_id} 闭环 | 共处置 {len(ctx.anomalies)} 个异常")
                return report
        except Exception as e:  # noqa: BLE001
            print(f"✗ 任务 {task_id} 异常: {type(e).__name__}: {e}")
            ctx.transition("closed", "Orchestrator", f"异常终止:{e}")
            raise


class SentryAgent:
    """巡检 Agent / Worker。职能:多源聚合、异常识别、降噪定级。"""
    IDENTITY = "Sentry · 巡检员"

    def detect(self, ctx: TaskContext) -> None:
        print(f"  🔍 [Sentry 巡检] 检测范围:{ctx.scope}")
        result = skills.anomaly_detect(
            store_ids=ctx.scope.get("store_ids"),
            data_sources=ctx.scope.get("data_sources"),
            trace_id=ctx.trace_id,
        )
        ctx.anomalies = result["anomalies"]
        if result.get("degraded"):
            print(f"     ⚠ 数据源降级,进入降噪模式:{result.get('error')}")
        # 高危优先(已按严重度排序)
        high = [a for a in ctx.anomalies if a["severity"] in ("高", "严重")]
        print(f"     检出 {len(ctx.anomalies)} 个异常(高危 {len(high)} 个)")


class DiagnoserAgent:
    """诊断 Agent / Worker。职能:跨店对标、维度下钻、根因定位。差异化核心。"""
    IDENTITY = "Diagnoser · 运营专家"

    def diagnose(self, anomaly: dict, ctx: TaskContext, retry: bool = False) -> None:
        print(f"  🩺 [Diagnoser 诊断] {anomaly['type']}@{anomaly['store_id']}" + ("(二次)" if retry else ""))
        # 选择对标指标
        metric_map = {"冷柜超温": "temp", "缺货": "stockout_rate", "低库存": "stockout_rate",
                      "价签不一致": "price_mismatch_rate", "临期": "loss_rate"}
        metric = metric_map.get(anomaly["type"], "stockout_rate")
        bench = None
        if metric in ("temp", "stockout_rate", "price_mismatch_rate"):
            bench = skills.cross_store_benchmark(anomaly["store_id"], metric, trace_id=ctx.trace_id)
            print(f"     跨店对标:{bench.get('conclusion')} (zscore={bench.get('zscore')})")
        rc = skills.rootcause_drilldown(anomaly, bench, trace_id=ctx.trace_id)
        print(f"     根因:{rc['hypothesis']} (置信度 {rc['confidence']})")
        # 更新/追加根因到上下文(去重:同 anomaly_id 覆盖)
        ctx.root_causes = [r for r in ctx.root_causes if r.get("anomaly_id") != rc["anomaly_id"]]
        ctx.root_causes.append(rc)


class ExecutorAgent:
    """处置 Agent / Worker。职能:方案生成、执行、审批触发、回滚。"""
    IDENTITY = "Executor · 店务专员"

    def handle(self, anomaly: dict, ctx: TaskContext) -> None:
        atype = anomaly["type"]
        sid = anomaly["store_id"]
        print(f"  🔧 [Executor 处置] {atype}@{sid}")
        action: dict
        if atype == "冷柜超温":
            action = self._handle_coldchain(anomaly, ctx)
        elif atype in ("缺货", "低库存"):
            action = self._handle_stockout(anomaly, ctx)
        elif atype == "价签不一致":
            action = self._handle_price(anomaly, ctx)
        elif atype == "临期":
            action = self._handle_expiry(anomaly, ctx)
        else:
            action = {"type": "manual", "note": "无自动处置,转人工"}
        ctx.actions.append(action)

    def _handle_coldchain(self, anomaly: dict, ctx: TaskContext) -> dict:
        # 维修工单(>2000 走审批)
        budget = 2500.0
        apr = mcp.create_approval(f"{anomaly['store_id']}冷柜维修", "workorder",
                                  {"budget": budget, "fault": "压缩机故障"}, ["店长"])
        apr_id = apr["rows"]["approval_id"] if isinstance(apr["rows"], dict) else apr["rows"][0]["approval_id"]
        wo = skills.work_order_dispatch(
            anomaly["store_id"], f"FROST-{anomaly['store_id']}",
            "压缩机/制冷故障", anomaly["severity"], budget,
            approval_id=apr_id, trace_id=ctx.trace_id,
        )
        return {"type": "work_order", "anomaly_type": "冷柜超温",
                "approval_id": apr_id, "workorder": wo, "executed": not wo.get("blocked", False)}

    def _handle_stockout(self, anomaly: dict, ctx: TaskContext) -> dict:
        order = skills.restock_order_gen(
            anomaly["store_id"], urgency="紧急",
            sku_list=[anomaly["evidence"].get("sku_id")] if anomaly["evidence"].get("sku_id") else None,
            trace_id=ctx.trace_id,
        )
        executed = not order.get("need_approval", False)
        if order.get("need_approval"):
            apr = mcp.create_approval(f"{anomaly['store_id']}补货单", "restock",
                                      {"total": order.get("total_amount")}, ["采购"])
            executed = apr["rows"].get("status") == "approved" if isinstance(apr["rows"], dict) else True
        return {"type": "restock", "anomaly_type": anomaly["type"],
                "order": order, "executed": executed}

    def _handle_price(self, anomaly: dict, ctx: TaskContext) -> dict:
        # 改价(批量>20 走审批;此处 demo 单 SKU)
        items = [{"sku_id": anomaly["evidence"]["sku_id"],
                  "new_price": anomaly["evidence"]["system_price"]}]
        apr = mcp.create_approval(f"{anomaly['store_id']}价签纠正", "price_change",
                                  {"items": items}, ["店长"])
        apr_id = apr["rows"]["approval_id"] if isinstance(apr["rows"], dict) else apr["rows"][0]["approval_id"]
        res = mcp.apply_price_change(anomaly["store_id"], items,
                                     idempotency_key=f"{ctx.trace_id}:{anomaly['anomaly_id']}",
                                     approval_ticket=apr_id)
        return {"type": "price_change", "anomaly_type": "价签不一致",
                "approval_id": apr_id, "result": res["rows"], "executed": not res.get("degraded", False)}

    def _handle_expiry(self, anomaly: dict, ctx: TaskContext) -> dict:
        mcp.send_notice(f"store_{anomaly['store_id']}", "expiry_alert", {
            "title": f"临期商品处理 {anomaly['evidence'].get('sku_id')}",
            "action": "贴临期标签/移至待售区",
        })
        return {"type": "notice", "anomaly_type": "临期", "executed": True}


class AuditorAgent:
    """稽核 Agent / Worker。职能:恢复验证、效果评估、复盘沉淀(飞轮引擎)。"""
    IDENTITY = "Auditor · 稽核员"

    def verify(self, anomaly: dict, ctx: TaskContext) -> bool:
        print(f"  ✅ [Auditor 验证] {anomaly['type']}@{anomaly['store_id']}")
        atype = anomaly["type"]
        # demo:规则核验(生产换 IoT 复测/POS 复查)
        if atype == "冷柜超温":
            # 模拟:工单完成后温度回落
            ok = any(a.get("type") == "work_order" and a.get("executed") for a in ctx.actions
                     if a.get("anomaly_type") == "冷柜超温")
            result = "resolved" if ok else "failed"
        elif atype in ("缺货", "低库存"):
            ok = any(a.get("type") == "restock" and a.get("executed") for a in ctx.actions
                     if a.get("anomaly_type") in ("缺货", "低库存"))
            result = "resolved" if ok else "failed"
        elif atype == "价签不一致":
            ok = any(a.get("type") == "price_change" and a.get("executed") for a in ctx.actions
                     if a.get("anomaly_type") == "价签不一致")
            result = "resolved" if ok else "failed"
        else:
            result = "resolved"
            ok = True
        print(f"     验证结果:{result}")
        # 记录到上下文(按 anomaly_id)
        rec = {"anomaly_id": anomaly["anomaly_id"], "result": result,
               "confidence": 0.9 if ok else 0.4, "method": "规则核验"}
        existing = ctx.validation or {}
        existing_by_id = existing.get("by_anomaly", {})
        existing_by_id[anomaly["anomaly_id"]] = rec
        ctx.validation = {"by_anomaly": existing_by_id, "latest": rec}
        return ok

    def review(self, ctx: TaskContext) -> dict:
        print(f"  📝 [Auditor 复盘] 沉淀知识 + Skill 建议")
        report = skills.review_report(ctx.snapshot(), trace_id=ctx.trace_id)
        ctx.review = report
        return report
