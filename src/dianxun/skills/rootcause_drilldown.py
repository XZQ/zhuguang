"""S3. rootcause-drilldown 维度下钻根因定位。

九要素（详见 skills/rootcause-drilldown/SKILL.md）：
  用途    对异常做维度下钻(门店×品类×时段×供应商),定位可疑根因,输出带证据的根因报告
  输入    anomaly_id, metric, candidate_dimensions?
  输出    RootCauseReport{hypothesis, confidence, drilldown_path, contributing_factors, check_plan}
  安全    只读;供应商信息仅总部角色;禁止把诊断结论直接写回业务系统
  复用    高,"指标异动归因"可复用到电商/制造/物流
  协同    诊断 Diagnoser 产出 → 上下文传处置 Executor;报告全文写审计库供稽核

被谁调用:诊断 Diagnoser Agent
关键:多假设并列输出 top3,知识库无命中明确"无历史案例"避免幻觉
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from .. import mcp, trace
from ..domain import Hypothesis
from .contracts import enforce_output_contract

if TYPE_CHECKING:
    from ..knowledge import KnowledgeService
    from ..mcp.p0 import MCPService


def rootcause_drilldown(
    anomaly: dict, benchmark: dict | None = None, trace_id: str | None = None
) -> dict:
    """对单个异常做根因下钻。

    Args:
        anomaly: anomaly_detect 的输出项 {anomaly_id, store_id, type, evidence, ...}
        benchmark: cross_store_benchmark 的对标结论(可选,增强根因判断)
        trace_id: 关联 trace

    Returns:
        RootCauseReport
    """
    tid = trace_id or trace.new_trace_id()
    atype = anomaly.get("type", "")
    with trace.span(
        "rootcause-drilldown",
        "skill",
        tid,
        input={"anomaly_id": anomaly.get("anomaly_id"), "type": atype},
    ) as sp:
        # 按异常类型分发到不同根因逻辑
        if atype == "冷柜超温":
            report = _drill_coldchain(anomaly, benchmark, tid)
        elif atype in ("缺货", "低库存"):
            report = _drill_stockout(anomaly, benchmark, tid)
        elif atype == "价签不一致":
            report = _drill_price(anomaly, benchmark, tid)
        elif atype == "临期":
            report = _drill_expiry(anomaly, benchmark, tid)
        else:
            report = _drill_generic(anomaly, benchmark, tid)

        sp.output = {"hypothesis": report["hypothesis"], "confidence": report["confidence"]}
        return report


def _drill_coldchain(anomaly: dict, bench: dict | None, tid: str) -> dict:
    """冷柜超温根因:借跨店对标排除环境因素,定位设备故障。"""
    ev = anomaly.get("evidence", {})
    hypotheses: list[dict] = []

    # 假设1: 设备故障(对标店同型号正常 → 排除环境)
    if bench and bench.get("conclusion") == "单店孤立异常":
        hypotheses.append(
            {
                "hypothesis": "压缩机/制冷组件故障",
                "confidence": 0.85,
                "reasoning": (
                    f"同商圈对标店温度正常(p50={bench.get('p50')}℃),排除天气/环境因素,"
                    f"目标店 max_temp={ev.get('max_temp')}℃ 显著偏高"
                    f"(zscore={bench.get('zscore')})"
                ),
            }
        )
    else:
        hypotheses.append(
            {
                "hypothesis": "疑似设备故障(需对标确认)",
                "confidence": 0.6,
                "reasoning": f"目标店温度 {ev.get('max_temp')}℃ 超阈值,缺对标数据无法排除环境因素",
            }
        )

    # 假设2: 配置问题(目标温度设错)——检查是否集群性
    if bench and bench.get("conclusion") == "集群性异常":
        hypotheses.append(
            {
                "hypothesis": "目标温度配置错误或环境温升",
                "confidence": 0.7,
                "reasoning": f"对标店也普遍超温(mean={bench.get('mean')}℃),倾向系统性因素",
            }
        )

    hypotheses.sort(key=lambda h: h["confidence"], reverse=True)
    # 联动:检查关联临期商品
    res = mcp.query_expiry(anomaly["store_id"], within_days=3)
    related = [r["sku_id"] for r in res["rows"]] if not res["degraded"] else []

    return {
        "report_id": "rc_" + uuid.uuid4().hex[:10],
        "anomaly_id": anomaly.get("anomaly_id"),
        "store_id": anomaly["store_id"],
        "type": anomaly["type"],
        "hypothesis": hypotheses[0]["hypothesis"],
        "confidence": hypotheses[0]["confidence"],
        "alternatives": hypotheses[1:],
        "drilldown_path": ["门店", "设备型号", "对标同商圈", "环境因素排除"],
        "contributing_factors": {
            "max_temp": ev.get("max_temp"),
            "benchmark_conclusion": bench.get("conclusion") if bench else None,
            "related_near_expiry_skus": related,
        },
        "check_plan": {
            "next_actions": ["生成维修工单(若金额>2000走审批)", "临期商品移至常温待售区"],
            "validation": "维修后 2 小时温度回基线",
        },
        "rag_hits": [],  # demo 无历史案例;真实环境从知识库检索
    }


def _drill_stockout(anomaly: dict, bench: dict | None, tid: str) -> dict:
    """缺货根因。"""
    ev = anomaly.get("evidence", {})
    hypothesis = "补货不及时/供应商断供"
    confidence = 0.7
    if bench and bench.get("zscore", 0) > 2:
        hypothesis = "单店补货流程异常(对标店同 SKU 库存正常)"
        confidence = 0.8
    return {
        "report_id": "rc_" + uuid.uuid4().hex[:10],
        "anomaly_id": anomaly.get("anomaly_id"),
        "store_id": anomaly["store_id"],
        "type": anomaly["type"],
        "hypothesis": hypothesis,
        "confidence": confidence,
        "alternatives": [],
        "drilldown_path": ["门店", "SKU", "供应商", "补货周期"],
        "contributing_factors": {"sku_id": ev.get("sku_id"), "stock": ev.get("stock")},
        "check_plan": {"next_actions": ["生成补货单"], "validation": "补货后库存 ≥ safety_stock"},
        "rag_hits": [],
    }


def _drill_price(anomaly: dict, bench: dict | None, tid: str) -> dict:
    """价签不一致根因。"""
    ev = anomaly.get("evidence", {})
    return {
        "report_id": "rc_" + uuid.uuid4().hex[:10],
        "anomaly_id": anomaly.get("anomaly_id"),
        "store_id": anomaly["store_id"],
        "type": anomaly["type"],
        "hypothesis": "促销价签未同步更新/人工贴错",
        "confidence": 0.82,
        "alternatives": [{"hypothesis": "系统价下发延迟", "confidence": 0.5}],
        "drilldown_path": ["门店", "SKU", "系统价 vs 价签 vs 收银价"],
        "contributing_factors": ev,
        "check_plan": {
            "next_actions": ["批量改价(>20SKU走审批)", "重新打印价签"],
            "validation": "三方价格一致",
        },
        "rag_hits": [],
    }


def _drill_expiry(anomaly: dict, bench: dict | None, tid: str) -> dict:
    return {
        "report_id": "rc_" + uuid.uuid4().hex[:10],
        "anomaly_id": anomaly.get("anomaly_id"),
        "store_id": anomaly["store_id"],
        "type": anomaly["type"],
        "hypothesis": "动销不足导致临期积压",
        "confidence": 0.65,
        "alternatives": [],
        "drilldown_path": ["门店", "品类", "动销率"],
        "contributing_factors": anomaly.get("evidence", {}),
        "check_plan": {
            "next_actions": ["贴临期标签/移待售区", "生成促销"],
            "validation": "商品售出或下架",
        },
        "rag_hits": [],
    }


def _drill_generic(anomaly: dict, bench: dict | None, tid: str) -> dict:
    return {
        "report_id": "rc_" + uuid.uuid4().hex[:10],
        "anomaly_id": anomaly.get("anomaly_id"),
        "store_id": anomaly.get("store_id", ""),
        "type": anomaly.get("type", "未知"),
        "hypothesis": "待进一步分析",
        "confidence": 0.4,
        "alternatives": [],
        "drilldown_path": [],
        "contributing_factors": anomaly.get("evidence", {}),
        "check_plan": {"next_actions": ["人工介入"], "validation": ""},
        "rag_hits": [],
    }


@enforce_output_contract("rootcause-drilldown")
def diagnose_coldchain_hypotheses(
    *,
    service: MCPService,
    incident_id: str,
    store_id: str,
    device_id: str,
    trace_id: str,
    knowledge: KnowledgeService | None = None,
) -> dict[str, Any]:
    """Build evidence-linked Top-K hypotheses from the stateful device context."""
    with trace.span(
        "rootcause-drilldown",
        "skill",
        trace_id,
        input={"incident_id": incident_id, "device_id": device_id},
    ) as sp:
        with trace.span(
            "query_device_context",
            "mcp",
            trace_id,
            input={"device_id": device_id, "facets": ["health", "door", "power", "temperature"]},
        ) as query_span:
            response = service.query_device_context(
                store_id=store_id,
                device_id=device_id,
                incident_id=incident_id,
                facets=["health", "door", "power", "temperature", "maintenance"],
                actor="Diagnoser",
            )
            query_span.output = {
                "ok": response["ok"],
                "request_id": response["request_id"],
                "partial": response["partial"],
            }
        if not response["ok"]:
            result = {
                "hypotheses": [
                    Hypothesis(
                        hypothesis_id=f"{incident_id}:insufficient-evidence",
                        label="insufficient_evidence",
                        confidence=0.2,
                        missing_evidence=["device_context"],
                        next_checks=["request_manual_measurement", "retry_device_query"],
                        policy_notes=["root_cause_not_confirmed"],
                    )
                ],
                "evidence": [],
                "quality": "partial",
                "rag": {"status": "disabled", "hits": []},
            }
            sp.output = {"quality": "partial", "top": "insufficient_evidence"}
            return result

        device = response["data"]["devices"][0]
        evidence = response["data"].get("evidence", [])
        evidence_ids = [item["evidence_id"] for item in evidence]
        manual_evidence = service.store.list_manual_evidence(incident_id=incident_id)
        manual_evidence_ids = [item["evidence_id"] for item in manual_evidence]
        health = device.get("health", {})
        power_on = device.get("power", {}).get("state") == "on"
        door_closed = device.get("door", {}).get("state") == "closed"
        compressor_stalled = health.get("compressor_state") in {"stalled", "fault", "off"}
        equipment_normal = (
            health.get("state") == "normal"
            and health.get("compressor_state") == "running"
            and power_on
            and door_closed
        )
        readings = device.get("temperature_series", [])
        trusted_readings = [
            item for item in readings if str(item.get("quality", "good")).lower() == "good"
        ]
        questionable_readings = [item for item in readings if item not in trusted_readings]
        maximum = float(service.policy.policy["temperature"]["refrigerated_max_celsius"])
        trusted_over = any(float(item["temp_c"]) > maximum for item in trusted_readings)
        questionable_over = any(float(item["temp_c"]) > maximum for item in questionable_readings)
        manual_temperatures = [
            float(metadata["temp_c"])
            for item in manual_evidence
            if (metadata := (item.get("metadata") or {})).get("temp_c") is not None
        ]
        manual_normal = bool(manual_temperatures) and all(
            temperature <= maximum for temperature in manual_temperatures
        )

        compressor_confidence = 0.94 if power_on and door_closed and compressor_stalled else 0.16
        door_confidence = 0.91 if not door_closed and power_on else 0.08
        power_confidence = 0.91 if not power_on else 0.05
        if questionable_over and equipment_normal and manual_normal and not trusted_over:
            sensor_confidence = 0.96
            sensor_missing: list[str] = ["backup_sensor"]
            sensor_support = [*evidence_ids, *manual_evidence_ids]
        elif questionable_over and equipment_normal:
            sensor_confidence = 0.58
            sensor_missing = ["backup_sensor", "manual_measurement"]
            sensor_support = evidence_ids
        else:
            sensor_confidence = 0.14
            sensor_missing = ["backup_sensor"]
            sensor_support = []
        hypotheses = [
            Hypothesis(
                hypothesis_id=f"{incident_id}:compressor-failure",
                label="compressor_failure",
                confidence=compressor_confidence,
                supporting_evidence_ids=evidence_ids if compressor_confidence >= 0.8 else [],
                contradicting_evidence_ids=[],
                missing_evidence=["compressor_current"] if compressor_confidence < 0.8 else [],
                next_checks=["inspect_compressor", "confirm_recovery_samples"],
                policy_notes=["cross_store_benchmark_is_supporting_only"],
            ),
            Hypothesis(
                hypothesis_id=f"{incident_id}:door-left-open",
                label="door_left_open",
                confidence=door_confidence,
                supporting_evidence_ids=[] if door_closed else evidence_ids,
                contradicting_evidence_ids=evidence_ids if door_closed else [],
                missing_evidence=["door_event_history"],
                next_checks=["inspect_door_seal"],
            ),
            Hypothesis(
                hypothesis_id=f"{incident_id}:power-failure",
                label="power_failure",
                confidence=power_confidence,
                supporting_evidence_ids=[] if power_on else evidence_ids,
                contradicting_evidence_ids=evidence_ids if power_on else [],
                missing_evidence=["voltage_history"],
                next_checks=["inspect_power_quality"],
            ),
            Hypothesis(
                hypothesis_id=f"{incident_id}:sensor-fault",
                label="sensor_fault",
                confidence=sensor_confidence,
                supporting_evidence_ids=sensor_support,
                contradicting_evidence_ids=evidence_ids if trusted_over else [],
                missing_evidence=sensor_missing,
                next_checks=["compare_backup_sensor", "request_manual_measurement"],
                policy_notes=["suspect_readings_cannot_prove_product_exposure"],
            ),
        ]
        hypotheses.sort(key=lambda item: item.confidence, reverse=True)
        rag: dict[str, Any] = {"status": "disabled", "hits": []}
        if knowledge is not None:
            incident = service.store.get_incident(incident_id) or {}
            query = " ".join(
                [
                    "冷柜失温",
                    str(device.get("model", "")),
                    str(health.get("state", "")),
                    str(health.get("compressor_state", "")),
                    hypotheses[0].label,
                ]
            )
            with trace.span(
                "knowledge-search",
                "rag",
                trace_id,
                input={"incident_id": incident_id, "top_k": 3},
            ) as rag_span:
                rag = knowledge.search(
                    tenant_id=str(incident.get("tenant_id", "demo")),
                    query=query,
                    top_k=3,
                )
                rag_span.output = {
                    "status": rag["status"],
                    "hit_count": len(rag["hits"]),
                    "knowledge_ids": [item["knowledge_id"] for item in rag["hits"]],
                }
        result = {
            "hypotheses": hypotheses[:3],
            "evidence": evidence,
            "quality": "partial" if questionable_readings or not evidence else "good",
            "rag": rag,
            "data_quality": {
                "trusted_readings": len(trusted_readings),
                "excluded_readings": len(questionable_readings),
                "manual_measurements": len(manual_temperatures),
            },
        }
        sp.output = {
            "quality": result["quality"],
            "top": hypotheses[0].label,
            "top_confidence": hypotheses[0].confidence,
        }
        return result
