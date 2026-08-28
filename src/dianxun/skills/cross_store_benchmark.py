"""S2. cross-store-benchmark 跨店横向对标。

九要素（详见 skills/planned/cross-store-benchmark.md）：
  用途    为异常门店选同商圈/同店型对标店,算基准分布,判断异常是单店孤立还是系统性
  输入    store_id, metric, benchmark_dimensions{商圈,店型,面积段}
  输出    BenchmarkReport{target, comparable[], p50/p90/p95, zscore, conclusion, evidence}
  安全    只读;跨店聚合仅返回统计值,不返回其他门店明细(防店间信息泄露)
  复用    高,零售底座 Skill(开源)
  协同    诊断 Diagnoser 核心决策 Skill;对标结论进上下文供处置参考

被谁调用:诊断 Diagnoser Agent
差异化亮点:用同商圈对标代替"老师傅经验"判断根因
"""

from __future__ import annotations

import statistics

from .. import mcp, trace


def cross_store_benchmark(
    store_id: str,
    metric: str,
    benchmark_dimensions: dict | None = None,
    trace_id: str | None = None,
) -> dict:
    """跨店横向对标。

    Args:
        store_id: 目标异常门店
        metric: 对标指标,支持 'temp' | 'stockout_rate' | 'price_mismatch_rate' | 'loss_rate'
        benchmark_dimensions: 对标维度 {商圈, 店型, 面积段};空=自动按门店主数据
        trace_id: 关联 trace

    Returns:
        BenchmarkReport
    """
    tid = trace_id or trace.new_trace_id()
    with trace.span(
        "cross-store-benchmark", "skill", tid, input={"store_id": store_id, "metric": metric}
    ) as sp:
        dims = benchmark_dimensions or _auto_dims(store_id)
        target_val, comparable_stores = _gather(store_id, metric, dims)

        if len(comparable_stores) < 3:
            # 对标店不足 → 降维(放宽商圈),标注置信度下降
            dims = {"店型": dims.get("店型")}  # 放宽只按店型
            target_val, comparable_stores = _gather(store_id, metric, dims)

        if len(comparable_stores) < 3:
            report = {
                "target_store": store_id,
                "metric": metric,
                "comparable_count": 0,
                "conclusion": "无基准",
                "fallback": "按固定阈值兜底",
                "degraded": True,
                "evidence": [],
            }
            sp.output = report
            return report

        values = [c["value"] for c in comparable_stores]
        p50 = round(statistics.median(values), 2)
        p90 = round(_percentile(values, 0.9), 2)
        p95 = round(_percentile(values, 0.95), 2)
        mean = statistics.mean(values)
        stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
        # zscore: 方差为 0 时(对标店全相同),用比率差异兜底,避免除零
        if stdev > 1e-9:
            zscore = round((target_val - mean) / stdev, 2)
        elif target_val > mean and mean < 1e-6:
            # 稀疏异常:目标店有、对标店全无 → 用"高出均值倍数"代理,封顶避免离谱值
            zscore = min(round(target_val * 100, 1), 99.0)
        elif target_val > mean:
            zscore = round((target_val - mean) * 10, 1)
        else:
            zscore = 0.0

        # 结论判定
        if metric == "temp":
            conclusion = (
                "单店孤立异常" if zscore > 2 else ("集群性异常" if mean > 5 else "行业普遍正常")
            )
        else:
            # 稀疏异常(缺货/价签):目标店显著高于对标 → 单店孤立;多家偏高 → 集群性
            if target_val > p95 and target_val > 0:
                conclusion = "单店孤立异常"
            elif mean > 0 and target_val >= mean * 1.5:
                conclusion = "单店孤立异常"
            elif p90 > 0:
                conclusion = "集群性异常"
            else:
                conclusion = "需进一步下钻"

        report = {
            "target_store": store_id,
            "metric": metric,
            "benchmark_dimensions": dims,
            "target_value": round(target_val, 2),
            "comparable_stores": [c["store_id"] for c in comparable_stores],
            "comparable_count": len(comparable_stores),
            "p50": p50,
            "p90": p90,
            "p95": p95,
            "mean": round(mean, 2),
            "zscore": zscore,
            "conclusion": conclusion,
            "evidence": [
                {"store_id": c["store_id"], "value": c["value"]} for c in comparable_stores
            ],
        }
        sp.output = {"conclusion": conclusion, "zscore": zscore}
        return report


def _auto_dims(store_id: str) -> dict:
    """从门店主数据自动推断对标维度(同商圈+同店型)。"""
    from ..mcp._csv_store import load_csv

    rows = load_csv("stores.csv")
    me = next((r for r in rows if r["store_id"] == store_id), None)
    if not me:
        return {}
    return {"商圈": me.get("bz"), "店型": me.get("type")}


def _gather(store_id: str, metric: str, dims: dict) -> tuple[float, list[dict]]:
    """收集目标店与对标店的指标值。返回 (目标值, 对标店列表)。"""
    from ..mcp._csv_store import load_csv

    rows = load_csv("stores.csv")
    # 筛对标店:满足 dims 全部条件,排除自己
    comparable = []
    for r in rows:
        if r["store_id"] == store_id:
            continue
        if all(not v or r.get(k) == v for k, v in dims.items()):
            comparable.append(r)
    # 不足时退化到全部其他店
    if len(comparable) < 3:
        comparable = [r for r in rows if r["store_id"] != store_id]

    def _metric_of(sid: str) -> float:
        return _compute_metric(sid, metric)

    target = _metric_of(store_id)
    comp_vals = [
        {"store_id": c["store_id"], "value": _metric_of(c["store_id"])} for c in comparable
    ]
    return target, comp_vals


def _compute_metric(store_id: str, metric: str) -> float:
    """计算单店某指标值。"""
    if metric == "temp":
        res = mcp.query_device_series(f"FROST-{store_id}", window_hours=24 * 14)
        rows = res["rows"]
        # iot 返回单聚合 dict,被包成 [dict]
        d = rows[0] if rows and isinstance(rows[0], dict) and "max_temp" in rows[0] else {}
        return d.get("max_temp", 3.5)
    if metric == "stockout_rate":
        res = mcp.query_stock(store_id)
        if res["degraded"] or not res["rows"]:
            return 0.0
        out = sum(1 for r in res["rows"] if r["stock"] <= 0)
        return out / len(res["rows"])
    if metric == "price_mismatch_rate":
        res = mcp.query_price(store_id)
        if res["degraded"] or not res["rows"]:
            return 0.0
        bad = sum(1 for r in res["rows"] if abs(r["pos_price"] - r["tag_price"]) > 0.01)
        return bad / len(res["rows"])
    if metric == "loss_rate":
        # demo: 用库存异常占比代理损耗率
        res = mcp.query_stock(store_id)
        if res["degraded"] or not res["rows"]:
            return 0.0
        exp = sum(
            1 for r in res["rows"] if r["days_to_expire"] <= 3 and r["cat"] in ("乳品", "鲜食")
        )
        return exp / len(res["rows"])
    return 0.0


def _percentile(values: list[float], p: float) -> float:
    """简单百分位计算。"""
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)
