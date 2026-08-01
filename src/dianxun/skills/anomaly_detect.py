"""S1. anomaly-detect 多源异常检测与降噪定级。

九要素(详见 skills/anomaly-detect.md):
  用途    聚合多源数据,识别异常事件、降噪并定级
  输入    window_start/window_end, store_ids?, data_sources?, thresholds?
  输出    AnomalyList[{anomaly_id, store_id, type, severity, confidence, evidence, ...}]
  调用    定时调度/事件触发;数据源健康检查通过
  失败    单源不可用→跳过标 partial;全不可用→空清单+degraded;LLM 解析异常→规则兜底
  安全    只读,无写权限;聚合数据不透传 PII;置信度过滤防刷屏
  复用    高,连锁业态通用(底座 Skill,开源)
  协同    巡检 Sentry 看家 Skill;输出喂诊断 Diagnoser,写共享上下文供稽核

被谁调用:巡检 Sentry Agent
"""

from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any

from .. import mcp
from .. import trace

# 默认阈值(可被 thresholds 参数覆盖)
_DEFAULTS = {
    "cold_temp_alarm": 5.0,      # 冷柜温度告警阈值(℃)
    "stockout_ratio": 0.0,       # 缺货: stock=0
    "low_stock_ratio": 0.5,      # 低库存: stock < safety_stock*0.5
    "expiry_days": 3,            # 临期阈值
    "price_mismatch_eps": 0.01,  # 价签不一致容差(元)
    "min_confidence": 0.6,       # 最低置信度过滤(防刷屏)
}


def anomaly_detect(window: dict | None = None,
                   store_ids: list[str] | None = None,
                   data_sources: list[str] | None = None,
                   thresholds: dict | None = None,
                   trace_id: str | None = None) -> dict:
    """检测多源异常,返回带置信度的异常清单。

    Args:
        window: 检测时间窗 {start, end};空=全量(demo 数据为历史快照)
        store_ids: 门店列表;空=全部门店
        data_sources: 要检测的源 ['iot','wms','price'];空=全部
        thresholds: 阈值覆盖
        trace_id: 关联 trace(demo 用)

    Returns:
        {anomalies:[...], partial:bool, degraded:bool, checked_stores:[]}
    """
    tid = trace_id or trace.new_trace_id()
    with trace.span("anomaly-detect", "skill", tid,
                    input={"store_ids": store_ids, "sources": data_sources}) as sp:
        cfg = {**_DEFAULTS, **(thresholds or {})}
        sources = data_sources or ["iot", "wms", "price"]
        stores = store_ids or _all_stores()
        anomalies: list[dict] = []
        partial = False

        for sid in stores:
            if "iot" in sources:
                a = _check_coldchain(sid, cfg, tid)
                if a is None:
                    partial = True  # 单源降级
                elif a:
                    anomalies.extend(a)
            if "wms" in sources:
                a = _check_inventory(sid, cfg, tid)
                if a is None:
                    partial = True
                elif a:
                    anomalies.extend(a)
            if "price" in sources:
                a = _check_price(sid, cfg, tid)
                if a is None:
                    partial = True
                elif a:
                    anomalies.extend(a)

        # 全部源不可用 → degraded
        degraded = partial and not anomalies
        # 置信度过滤(防刷屏)
        anomalies = [a for a in anomalies if a["confidence"] >= cfg["min_confidence"]]
        # 严重度定级排序
        sev_order = {"严重": 4, "高": 3, "中": 2, "低": 1}
        anomalies.sort(key=lambda a: sev_order.get(a["severity"], 0), reverse=True)

        result = {
            "anomalies": anomalies,
            "count": len(anomalies),
            "partial": partial,
            "degraded": degraded,
            "checked_stores": stores,
            "checked_sources": sources,
        }
        sp.output = {"count": len(anomalies), "degraded": degraded}
        return result


def _all_stores() -> list[str]:
    """从门店主数据取全部门店。"""
    from ..mcp._csv_store import load_csv
    rows = load_csv("stores.csv")
    return [r["store_id"] for r in rows] if rows else [f"S{i:02d}" for i in range(1, 13)]


def _new_anomaly(store_id: str, atype: str, severity: str, confidence: float,
                 evidence: dict, matched_rule: str) -> dict:
    return {
        "anomaly_id": "an_" + uuid.uuid4().hex[:10],
        "store_id": store_id,
        "type": atype,                # 缺货/临期/价签/冷柜/低库存
        "severity": severity,         # 低/中/高/严重
        "confidence": round(confidence, 2),
        "evidence": evidence,
        "matched_rule": matched_rule,
        "detected_at": datetime.now().isoformat(timespec="seconds"),
    }


def _check_coldchain(store_id: str, cfg: dict, tid: str) -> list[dict] | None:
    """冷柜温度异常检测。返回 None 表示该源不可用(降级)。"""
    dev = mcp.query_device_series(f"FROST-{store_id}", window_hours=24 * 14)
    if dev["degraded"]:
        return None
    # iot 工具返回单个聚合 dict,被 ToolResult 包成 [dict];取首项
    rows = dev["rows"]
    d = rows[0] if rows and isinstance(rows[0], dict) and "readings" in rows[0] else {}
    if not d:
        return []
    temps = [r["temp_c"] for r in d.get("readings", [])]
    max_temp = d.get("max_temp", max(temps) if temps else 0)
    if max_temp <= cfg["cold_temp_alarm"]:
        return []
    over = [t for t in temps if t > cfg["cold_temp_alarm"]]
    over_ratio = len(over) / len(temps) if temps else 1.0
    sev = "严重" if over_ratio > 0.5 else "高"
    return [_new_anomaly(
        store_id, "冷柜超温", sev, 0.92,
        {"device_id": d.get("device_id", f"FROST-{store_id}"), "max_temp": max_temp,
         "avg_temp": d.get("avg_temp"), "over_ratio": round(over_ratio, 2),
         "threshold": cfg["cold_temp_alarm"], "window": "近14天"},
        "cold_temp_continuous_over_threshold",
    )]


def _check_inventory(store_id: str, cfg: dict, tid: str) -> list[dict] | None:
    """库存异常:缺货/低库存/临期。"""
    res = mcp.query_stock(store_id)
    if res["degraded"]:
        return None
    out: list[dict] = []
    for r in res["rows"]:
        if r["stock"] <= 0:
            out.append(_new_anomaly(
                store_id, "缺货", "高", 0.95,
                {"sku_id": r["sku_id"], "stock": 0, "safety_stock": r["safety_stock"]},
                "stock_zero",
            ))
        elif r["stock"] < r["safety_stock"] * cfg["low_stock_ratio"]:
            out.append(_new_anomaly(
                store_id, "低库存", "中", 0.75,
                {"sku_id": r["sku_id"], "stock": r["stock"],
                 "safety_stock": r["safety_stock"]},
                "stock_below_half_safety",
            ))
        if r["days_to_expire"] <= cfg["expiry_days"] and r["cat"] in ("乳品", "鲜食"):
            out.append(_new_anomaly(
                store_id, "临期", "中", 0.8,
                {"sku_id": r["sku_id"], "days_to_expire": r["days_to_expire"],
                 "cat": r["cat"]},
                "near_expiry",
            ))
    return out


def _check_price(store_id: str, cfg: dict, tid: str) -> list[dict] | None:
    """价签一致性:系统价 vs 货架价签 vs 收银价。"""
    res = mcp.query_price(store_id)
    if res["degraded"]:
        return None
    out: list[dict] = []
    eps = cfg["price_mismatch_eps"]
    for r in res["rows"]:
        # 收银价高于标价 = 严重(顾客被多收钱,合规风险)
        if abs(r["pos_price"] - r["tag_price"]) > eps:
            sev = "严重" if r["pos_price"] > r["tag_price"] else "中"
            out.append(_new_anomaly(
                store_id, "价签不一致", sev, 0.88,
                {"sku_id": r["sku_id"], "system_price": r["system_price"],
                 "tag_price": r["tag_price"], "pos_price": r["pos_price"]},
                "price_tag_pos_mismatch",
            ))
    return out
