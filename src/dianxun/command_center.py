"""Incident command center: a self-contained HTML view of the six M4 scenarios.

Runs the same deterministic baseline suite and renders one read-only HTML page that
puts agent handoffs, the device state chain, the batch state chain, evidence,
approvals, audits and the Auditor verdict on a single screen. The page has no
external dependencies (inline CSS/JS/SVG) so judges can open it offline.

Boundary: all data comes from real temporary SQLite/PolicyEngine plus stateful local
adapters and a fixed seed; the page demonstrates repository-internal deterministic
behavior, not a live deployment.
"""

from __future__ import annotations

import html
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from . import trace
from .adapters import LocalDemoAdapter
from .evaluation import (
    DEFAULT_EVIDENCE_DIR,
    DEFAULT_SCENARIO_DIR,
    P0_SCENARIO_FILES,
    PHASE_SPANS,
    _aggregate,
    _audit_succeeded,
    _evaluate_scenario,
)

DEFAULT_COMMAND_CENTER_PATH = DEFAULT_EVIDENCE_DIR / "command-center.html"

_SCENARIO_META = {
    "coldchain-compressor-failure": {
        "title": "A · 压缩机故障",
        "branch": "正常分支",
        "redline": "维修完成后仍须 Auditor 独立重查才能放行商品",
    },
    "coldchain-sensor-false-positive": {
        "title": "B · 传感器误报",
        "branch": "正常分支",
        "redline": "人工实测证伪疑似超温,只校准传感器,不误修压缩机",
    },
    "coldchain-door-left-open": {
        "title": "C · 柜门未关",
        "branch": "正常分支",
        "redline": "关门不等于可以放行,商品批次仍按暴露评估处置",
    },
    "coldchain-approval-timeout": {
        "title": "D · 审批超时",
        "branch": "失败分支",
        "redline": "维修未获授权:保持遏制并升级区域经理,而不是强行执行",
    },
    "coldchain-device-recovered-goods-unsafe": {
        "title": "E · 设备恢复但商品不安全",
        "branch": "失败分支",
        "redline": "设备恢复 ≠ 商品安全:Auditor 拒绝关闭,商品继续隔离待审",
    },
    "coldchain-workorder-query-partial": {
        "title": "F · 工单查询部分失败",
        "branch": "失败分支",
        "redline": "工单完成 ≠ 事件关闭:工具部分失败时保持遏制并阻断",
    },
}

_PHASE_LABELS = {
    "DETECT_CONTAIN": "1 发现与遏制",
    "DIAGNOSE_DECIDE": "2 诊断与决策",
    "EXECUTE": "3 处置执行",
    "VERIFY": "4 独立验证",
    "LEARN": "5 复盘演进",
}

_AGENT_LABELS = {
    "sentry": "Sentry 巡检",
    "executor-containment": "Executor 遏制",
    "diagnoser": "Diagnoser 诊断",
    "executor": "Executor 处置",
    "auditor": "Auditor 稽核",
    "executor-release": "Executor 放行",
    "review-report": "Auditor 复盘",
    "coldchain-orchestrator": "Orchestrator 总控",
}


def build_command_center(
    scenario_dir: str | Path = DEFAULT_SCENARIO_DIR,
    output_path: str | Path = DEFAULT_COMMAND_CENTER_PATH,
) -> Path:
    """Run the six baseline scenarios and render the command-center HTML."""
    scenario_root = Path(scenario_dir).resolve()
    details: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dianxun-cc-") as temporary:
        runtime_root = Path(temporary)
        for index, filename in enumerate(P0_SCENARIO_FILES, start=1):
            scenario_path = scenario_root / filename
            adapter = LocalDemoAdapter(
                db_path=runtime_root / f"scenario-{index}.db",
                trace_db_path=runtime_root / f"scenario-{index}.trace.db",
                scenario_path=scenario_path,
            )
            result = adapter.run()
            with trace.use_database(adapter.trace_db_path):
                trace_rows = trace.query_trace(result["trace_id"])
            rows.append(_evaluate_scenario(adapter, result, trace_rows))
            details.append(_collect_detail(adapter, result, trace_rows))
    seed = json.loads((scenario_root.parent / "seed.json").read_text(encoding="utf-8"))
    document = _render(details, rows, _aggregate(rows), seed["anchor_time"])
    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8", newline="\n")
    return target


def _collect_detail(
    adapter: LocalDemoAdapter,
    result: dict[str, Any],
    trace_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    case = result["incident"]
    incident_id = case["incident_id"]
    store = adapter.store
    scenario_id = result["scenario_id"]
    device = adapter.mcp.query_device_context(
        store_id=case["store_id"],
        device_id=case["affected_assets"][0],
        incident_id=incident_id,
        actor="Auditor",
    )["data"]["devices"][0]
    agent_spans = [
        {
            "name": row["name"],
            "label": _AGENT_LABELS.get(row["name"], row["name"]),
            "kind": row["kind"],
            "status": row["status"],
            "duration_ms": row["end_ms"] - row["start_ms"],
            "output": _span_output_brief(row),
        }
        for row in trace_rows
        if row["kind"] == "agent" and row["name"] != "coldchain-orchestrator"
    ]
    audits = store.list_audit_log(incident_id=incident_id)
    verification = result.get("verification") or {}
    return {
        "scenario_id": scenario_id,
        "meta": _SCENARIO_META.get(
            scenario_id, {"title": scenario_id, "branch": "-", "redline": ""}
        ),
        "final_state": {
            "incident_status": str(case["incident_status"]),
            "phase": str(case["phase"]),
            "work_status": str(case["work_status"]),
        },
        "acceptance": result["acceptance"],
        "phases": _phase_cards(result),
        "agent_spans": agent_spans,
        "device": {
            "device_id": device.get("device_id"),
            "health": device.get("health", {}),
            "series": device.get("temperature_series", []),
        },
        "batches": store.list_batches(batch_ids=case["affected_batches"]),
        "holds": store.list_sales_holds(incident_id=incident_id),
        "approvals": store.list_approvals(incident_id=incident_id),
        "workorders": store.list_workorders(incident_id=incident_id),
        "verifications": store.list_verifications(incident_id=incident_id),
        "verification": {
            "result": verification.get("result"),
            "failed_conditions": verification.get("failed_conditions", []),
            "partial_tools": verification.get("partial_tools", []),
            "attempts": verification.get("attempts", []),
            "checks": verification.get("checks", {}),
        },
        "audits": [
            {
                "tool_name": row["tool_name"],
                "actor": row["actor"],
                "ok": _audit_succeeded(row),
                "created_at": row["created_at"],
            }
            for row in audits
        ],
        "review": result.get("review"),
        "evidence_refs": len(case.get("evidence_refs", [])),
    }


def _span_output_brief(row: dict[str, Any]) -> str:
    try:
        output = json.loads(row["output_json"]) if row["output_json"] else None
    except json.JSONDecodeError:
        return ""
    if not isinstance(output, dict):
        return ""
    brief: list[str] = []
    for key in ("result", "detected", "severity", "top_hypothesis", "ok"):
        if key in output:
            brief.append(f"{key}={output[key]}")
    if output.get("failed_conditions"):
        brief.append(f"failed={','.join(output['failed_conditions'])}")
    return " ".join(str(item) for item in brief)[:120]


def _phase_cards(result: dict[str, Any]) -> list[dict[str, Any]]:
    phases = result["phases"]
    cards: list[dict[str, Any]] = []
    detect = phases.get("DETECT_CONTAIN") or {}
    if detect:
        containment = detect.get("containment") or {}
        cards.append(
            {
                "phase": "DETECT_CONTAIN",
                "points": [
                    f"严重度:{detect.get('severity', '-')}",
                    f"受影响批次:{len(detect.get('affected_batches', []))} 个",
                    f"停售遏制:{'成功' if containment.get('ok') else '未完成'}",
                ],
            }
        )
    diagnosis = phases.get("DIAGNOSE_DECIDE") or {}
    if diagnosis:
        hypotheses = diagnosis.get("hypotheses") or []
        top = hypotheses[0] if hypotheses else {}
        assessment = diagnosis.get("risk_assessment") or {}
        recommendations = [
            f"{item['batch_id'].split('-')[-2]}→{item['recommendation']}"
            for item in assessment.get("exposure_assessment", [])
        ]
        cards.append(
            {
                "phase": "DIAGNOSE_DECIDE",
                "points": [
                    f"Top-1 假设:{top.get('label', '-')}(置信度 {top.get('confidence', '-')})",
                    f"候选假设:{len(hypotheses)} 个,全部挂证据",
                    f"批次处置建议:{'; '.join(recommendations) if recommendations else '-'}",
                ],
            }
        )
    execute = phases.get("EXECUTE") or {}
    if execute:
        repair = execute.get("repair") or {}
        points = [f"维修工单:{repair.get('result', '-')}"]
        dispositions = execute.get("batch_dispositions") or []
        if dispositions:
            done = sum(1 for item in dispositions if item["result"] == "executed")
            points.append(f"批次处置:{done}/{len(dispositions)} 已执行")
        release = execute.get("sales_hold_release") or {}
        if release:
            points.append(f"停售放行:{release.get('result', '-')}")
        cards.append({"phase": "EXECUTE", "points": points})
    verification = result.get("verification") or {}
    if "VERIFY" in phases or verification:
        failed = verification.get("failed_conditions") or []
        partial = verification.get("partial_tools") or []
        points = [f"Auditor 判决:{verification.get('result', '-')}"]
        if failed:
            points.append(f"未通过条件:{', '.join(failed)}")
        if partial:
            points.append(f"工具部分失败:{', '.join(partial)}")
        attempts = verification.get("attempts") or []
        if len(attempts) > 1:
            points.append(f"独立重查 {len(attempts)} 轮")
        cards.append({"phase": "VERIFY", "points": points})
    review = result.get("review") or {}
    if review:
        summary = review.get("summary") or review.get("title") or ""
        points = [summary[:60] if summary else "复盘与知识候选已生成"]
        candidates = review.get("knowledge_candidates") or review.get("knowledge") or []
        if isinstance(candidates, list) and candidates:
            points.append(f"知识候选 {len(candidates)} 条(待人工审核)")
        cards.append({"phase": "LEARN", "points": points})
    return cards


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _badge(text: str, tone: str) -> str:
    return f'<span class="badge badge-{tone}">{_esc(text)}</span>'


def _render(
    details: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    metrics: dict[str, Any],
    anchor_time: str,
) -> str:
    kpis = [
        ("场景通过", f"{metrics['scenario_passed']}/{metrics['scenario_count']}"),
        ("Top-1 / Top-3", f"{metrics['top1_hits']}/{metrics['top3_hits']}"),
        ("错误关闭 / 错误放行", f"{metrics['erroneous_closures']} / {metrics['unsafe_releases']}"),
        (
            "未授权 / 未审批写",
            f"{metrics['unauthorized_business_writes']} / {metrics['unapproved_controlled_writes']}",
        ),
        (
            "Evidence 完整率",
            f"{metrics['complete_evidence_records']}/{metrics['evidence_records']}",
        ),
        ("Trace 覆盖", f"{metrics['covered_trace_phases']}/{metrics['expected_trace_phases']}"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-v">{_esc(value)}</div><div class="kpi-k">{_esc(label)}</div></div>'
        for label, value in kpis
    )
    tabs = []
    panels = []
    for index, detail in enumerate(details):
        active = " active" if index == 0 else ""
        tabs.append(
            f'<button class="tab{active}" data-panel="panel-{index}">{_esc(detail["meta"]["title"])}</button>'
        )
        panels.append(_render_panel(index, detail, rows[index], active))
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>逐光 · 事故指挥台</title>
<style>{_CSS}</style></head><body>
<header class="hero">
  <div>
    <h1>逐光 · 事故指挥台</h1>
    <p class="sub">六场景冷柜失温闭环 · 确定性本地评测 · 虚拟时钟锚点 {_esc(anchor_time)}</p>
  </div>
  <div class="redlines">
    <div class="redline">红线一:执行者不能自证成功,Auditor 必须独立重查</div>
    <div class="redline">红线二:设备恢复 ≠ 商品安全,工单完成 ≠ 事件关闭</div>
  </div>
</header>
<section class="kpis">{kpi_html}</section>
<nav class="tabs">{"".join(tabs)}</nav>
{"".join(panels)}
<footer class="foot">数据来自真实临时 SQLite/PolicyEngine、有状态本地 Adapter/ScenarioEngine 与固定 seed;仅证明仓库内确定性行为。</footer>
<script>{_JS}</script>
</body></html>
"""
    return "\n".join(line.rstrip() for line in html.splitlines()) + "\n"


def _render_panel(index: int, detail: dict[str, Any], row: dict[str, Any], active: str) -> str:
    state = detail["final_state"]
    passed = row["passed"]
    branch_tone = "ok" if detail["meta"]["branch"] == "正常分支" else "warn"
    state_tone = "ok" if state["incident_status"] == "CLOSED" else "warn"
    phase_html = _render_phase_lane(detail)
    device_html = _render_device(detail["device"])
    batches_html = _render_batches(detail)
    approvals_html = _render_approvals(detail["approvals"])
    verdict_html = _render_verdict(detail)
    audits_html = _render_audits(detail["audits"])
    mismatches = detail["acceptance"].get("mismatches", [])
    mismatch_html = (
        ""
        if not mismatches
        else '<div class="mismatch"><b>验收偏差:</b>' + _esc("; ".join(mismatches)) + "</div>"
    )
    return f"""
<section class="panel{active}" id="panel-{index}">
  <div class="panel-head">
    <h2>{_esc(detail["meta"]["title"])}</h2>
    <div class="badges">
      {_badge(detail["meta"]["branch"], branch_tone)}
      {_badge("验收通过" if passed else "验收未过", "ok" if passed else "bad")}
      {_badge(state["incident_status"], state_tone)}
      {_badge("阶段 " + state["phase"], "info")}
      {_badge(state["work_status"], "info")}
    </div>
  </div>
  <div class="redline-note">{_esc(detail["meta"]["redline"])}</div>
  {mismatch_html}
  <h3>五阶段闭环</h3>
  {phase_html}
  <h3>Agent 交接链</h3>
  {_render_handoff(detail["agent_spans"])}
  <div class="grid-2">
    <div>{device_html}</div>
    <div>{verdict_html}</div>
  </div>
  <h3>商品批次与停售</h3>
  {batches_html}
  <h3>审批</h3>
  {approvals_html}
  <h3>受控写审计</h3>
  {audits_html}
</section>
"""


def _render_phase_lane(detail: dict[str, Any]) -> str:
    cards = {card["phase"]: card["points"] for card in detail["phases"]}
    parts = []
    for phase in PHASE_SPANS:
        points = cards.get(phase)
        cls = "phase-card done" if points else "phase-card skip"
        body = (
            "<ul>" + "".join(f"<li>{_esc(point)}</li>" for point in points) + "</ul>"
            if points
            else '<div class="phase-none">未进入</div>'
        )
        parts.append(
            f'<div class="{cls}"><div class="phase-title">{_esc(_PHASE_LABELS[phase])}</div>{body}</div>'
        )
    return '<div class="phase-lane">' + '<div class="phase-arrow">→</div>'.join(parts) + "</div>"


def _render_handoff(spans: list[dict[str, Any]]) -> str:
    parts = []
    for span in spans:
        tone = "ok" if span["status"] == "ok" else "bad"
        brief = f'<div class="hop-brief">{_esc(span["output"])}</div>' if span["output"] else ""
        parts.append(
            f'<div class="hop hop-{tone}"><div class="hop-name">{_esc(span["label"])}</div>{brief}</div>'
        )
    return '<div class="handoff">' + '<div class="hop-arrow">→</div>'.join(parts) + "</div>"


def _render_device(device: dict[str, Any]) -> str:
    series = sorted(device["series"], key=lambda item: item["observed_at"])
    health = device["health"]
    svg = _temperature_svg(series)
    return f"""<h3>设备状态链 · {_esc(device["device_id"])}</h3>
<div class="card">
  <div class="device-health">
    {_badge("健康 " + str(health.get("state", "-")), "ok" if health.get("state") == "normal" else "bad")}
    {_badge("压缩机 " + str(health.get("compressor_state", "-")), "info")}
    {_badge("门 " + str(health.get("door_state", "-")), "info")}
  </div>
  {svg}
  <div class="legend">蓝线/蓝点=可信读数 · 橙点=suspect 读数(不参与主折线) · 红虚线=8°C 告警阈值</div>
</div>"""


def _temperature_svg(series: list[dict[str, Any]]) -> str:
    if not series:
        return '<div class="phase-none">无温度读数</div>'
    width, height, pad = 560, 170, 30
    times = [datetime.fromisoformat(item["observed_at"]) for item in series]
    temps = [float(item["temp_c"]) for item in series]
    t0, t1 = min(times), max(times)
    lo = min(min(temps), 7.0) - 0.5
    hi = max(max(temps), 8.5) + 0.5
    span_t = max((t1 - t0).total_seconds(), 1.0)

    def x(at: datetime) -> float:
        return pad + (at - t0).total_seconds() / span_t * (width - 2 * pad)

    def y(temp: float) -> float:
        return height - pad - (temp - lo) / (hi - lo) * (height - 2 * pad)

    trusted_segments: list[list[tuple[datetime, float]]] = []
    current_segment: list[tuple[datetime, float]] = []
    for at, temp, item in zip(times, temps, series, strict=True):
        if str(item.get("quality", "good")).lower() == "good":
            current_segment.append((at, temp))
        else:
            if current_segment:
                trusted_segments.append(current_segment)
                current_segment = []
    if current_segment:
        trusted_segments.append(current_segment)
    polylines = "".join(
        '<polyline points="{}" fill="none" stroke="#2563eb" stroke-width="2"/>'.format(
            " ".join(f"{x(at):.1f},{y(temp):.1f}" for at, temp in segment)
        )
        for segment in trusted_segments
        if len(segment) >= 2
    )
    dots = []
    for at, temp, item in zip(times, temps, series, strict=True):
        color = "#f59e0b" if str(item.get("quality", "good")).lower() != "good" else "#2563eb"
        dots.append(f'<circle cx="{x(at):.1f}" cy="{y(temp):.1f}" r="4" fill="{color}"/>')
        dots.append(
            f'<text x="{x(at):.1f}" y="{y(temp) - 8:.1f}" class="t-lbl" text-anchor="middle">{temp:.1f}</text>'
        )
    threshold_y = y(8.0)
    return f"""<svg viewBox="0 0 {width} {height}" class="temp-svg" role="img" aria-label="温度曲线">
<line x1="{pad}" y1="{threshold_y:.1f}" x2="{width - pad}" y2="{threshold_y:.1f}" stroke="#dc2626" stroke-dasharray="5 4" stroke-width="1.5"/>
{polylines}
{"".join(dots)}
<text x="{width - pad + 2}" y="{threshold_y + 4:.1f}" class="t-th">8°C</text>
</svg>"""


def _render_verdict(detail: dict[str, Any]) -> str:
    verdict = detail["verification"]
    result = verdict["result"] or "未验证"
    tone = {
        "verified": "ok",
        "release_ready": "info",
        "manual_review": "warn",
        "reopened": "bad",
    }.get(str(verdict["result"]), "info")
    rows = []
    for row in detail["verifications"]:
        ok = row["result"] == "passed"
        rows.append(
            "<tr>"
            f"<td>{_esc(row['subject'])}</td>"
            f"<td>{_badge('通过' if ok else '未过', 'ok' if ok else 'bad')}</td>"
            f"<td>{_esc(row['verifier'])}</td>"
            f"<td class='mono'>{_esc(row['verified_at'][11:19])}</td>"
            "</tr>"
        )
    checks_html = (
        "<table class='tbl'><thead><tr><th>验证主题</th><th>结果</th><th>验证者</th><th>时间</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        if rows
        else '<div class="phase-none">本分支无独立验证记录(维修未执行,提前等待)</div>'
    )
    extras = []
    if verdict["failed_conditions"]:
        extras.append(f"未通过条件:{_esc(', '.join(verdict['failed_conditions']))}")
    if verdict["partial_tools"]:
        extras.append(f"工具部分失败:{_esc(', '.join(verdict['partial_tools']))}")
    if len(verdict["attempts"]) > 1:
        extras.append(f"独立重查 {len(verdict['attempts'])} 轮(放行前 + 放行后)")
    extra_html = f"<div class='verdict-extra'>{' · '.join(extras)}</div>" if extras else ""
    return f"""<h3>Auditor 判决</h3>
<div class="card">
  <div class="verdict-head">{_badge(result, tone)}{_badge(f"证据引用 {detail['evidence_refs']} 条", "info")}</div>
  {extra_html}
  {checks_html}
</div>"""


def _render_batches(detail: dict[str, Any]) -> str:
    holds = {row["batch_id"]: row for row in detail["holds"]}
    rows = []
    for batch in detail["batches"]:
        hold = holds.get(batch["batch_id"], {})
        disposition = batch["disposition"]
        tone = {
            "released": "ok",
            "transferred": "info",
            "disposed": "warn",
            "quarantined": "bad",
        }.get(disposition, "info")
        hold_status = hold.get("status", "-")
        hold_tone = {"released": "ok", "active": "bad"}.get(hold_status, "info")
        safe = batch["safe_for_sale"]
        rows.append(
            "<tr>"
            f"<td class='mono'>{_esc(batch['batch_id'])}</td>"
            f"<td>{_badge(disposition, tone)}</td>"
            f"<td>{_badge('停售中' if hold_status == 'active' else hold_status, hold_tone)}</td>"
            f"<td>{_badge('安全' if safe else '不安全', 'ok' if safe else 'bad')}</td>"
            "</tr>"
        )
    return (
        "<table class='tbl'><thead><tr><th>批次</th><th>处置状态</th><th>停售</th><th>食用安全</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_approvals(approvals: list[dict[str, Any]]) -> str:
    if not approvals:
        return '<div class="phase-none">无审批记录</div>'
    rows = []
    for item in approvals:
        status = item["status"]
        tone = {"approved": "ok", "pending": "warn", "timeout": "bad", "rejected": "bad"}.get(
            status, "info"
        )
        rows.append(
            "<tr>"
            f"<td>{_esc(item.get('subject', item['approval_id']))}</td>"
            f"<td>{_badge(status, tone)}</td>"
            f"<td class='mono'>{_esc(str(item.get('amount') or '-'))}</td>"
            f"<td class='mono'>{_esc(str(item.get('deadline', '-'))[11:19])}</td>"
            "</tr>"
        )
    return (
        "<table class='tbl'><thead><tr><th>事项</th><th>状态</th><th>金额</th><th>截止</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_audits(audits: list[dict[str, Any]]) -> str:
    rows = []
    for item in audits:
        ok = item["ok"]
        rows.append(
            "<tr>"
            f"<td class='mono'>{_esc(item['tool_name'])}</td>"
            f"<td>{_esc(item['actor'])}</td>"
            f"<td>{_badge('成功' if ok else '被拒/失败', 'ok' if ok else 'bad')}</td>"
            f"<td class='mono'>{_esc(item['created_at'][11:19])}</td>"
            "</tr>"
        )
    return (
        "<table class='tbl'><thead><tr><th>工具</th><th>Actor</th><th>结果</th><th>时间</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#f6f8fb;color:#1f2937;line-height:1.55;padding:24px;max-width:1240px;margin:0 auto}
.hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;flex-wrap:wrap}
h1{font-size:26px;color:#0f2a5c}
.sub{color:#64748b;margin-top:4px;font-size:13px}
.redlines{display:flex;flex-direction:column;gap:8px}
.redline{background:#fef2f2;border:1px solid #fecaca;border-left:4px solid #dc2626;color:#991b1b;padding:8px 12px;border-radius:8px;font-size:13px;font-weight:600}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}
.kpi{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:12px 14px}
.kpi-v{font-size:20px;font-weight:700;color:#0f2a5c}
.kpi-k{font-size:12px;color:#64748b;margin-top:2px}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 16px}
.tab{border:1px solid #cbd5e1;background:#fff;border-radius:999px;padding:7px 14px;font-size:13px;cursor:pointer;color:#334155}
.tab.active{background:#0f2a5c;color:#fff;border-color:#0f2a5c}
.panel{display:none;background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:20px 22px}
.panel.active{display:block}
.panel-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
h2{font-size:19px;color:#0f2a5c}
h3{font-size:14px;color:#0f2a5c;margin:18px 0 8px}
.badges{display:flex;gap:6px;flex-wrap:wrap}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600;border:1px solid transparent;white-space:nowrap}
.badge-ok{background:#ecfdf5;color:#047857;border-color:#a7f3d0}
.badge-warn{background:#fffbeb;color:#b45309;border-color:#fde68a}
.badge-bad{background:#fef2f2;color:#b91c1c;border-color:#fecaca}
.badge-info{background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe}
.redline-note{margin-top:10px;background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;border-radius:8px;padding:8px 12px;font-size:13px;font-weight:600}
.mismatch{margin-top:8px;background:#fef2f2;border:1px solid #fecaca;color:#991b1b;border-radius:8px;padding:8px 12px;font-size:12px}
.phase-lane{display:flex;align-items:stretch;gap:6px;flex-wrap:wrap}
.phase-card{flex:1;min-width:170px;border:1px solid #e2e8f0;border-radius:12px;padding:10px 12px;background:#f8fafc}
.phase-card.done{border-top:3px solid #2563eb}
.phase-card.skip{opacity:.55}
.phase-title{font-weight:700;font-size:13px;color:#0f2a5c;margin-bottom:6px}
.phase-card ul{padding-left:16px;font-size:12px;color:#475569}
.phase-none{font-size:12px;color:#94a3b8;padding:6px 0}
.phase-arrow{align-self:center;color:#94a3b8;font-weight:700}
.handoff{display:flex;align-items:stretch;gap:6px;flex-wrap:wrap}
.hop{border-radius:12px;padding:8px 12px;min-width:120px;border:1px solid #e2e8f0;background:#f8fafc}
.hop-ok{border-top:3px solid #059669}
.hop-bad{border-top:3px solid #dc2626}
.hop-name{font-size:12px;font-weight:700;color:#0f2a5c}
.hop-brief{font-size:11px;color:#64748b;margin-top:3px;word-break:break-all}
.hop-arrow{align-self:center;color:#94a3b8}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:900px){.grid-2{grid-template-columns:1fr}}
.card{border:1px solid #e2e8f0;border-radius:12px;padding:12px 14px;background:#fbfdff}
.device-health{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.temp-svg{width:100%;height:auto}
.t-lbl{font-size:9px;fill:#475569}
.t-th{font-size:10px;fill:#dc2626;font-weight:700}
.legend{font-size:11px;color:#94a3b8;margin-top:4px}
.verdict-head{display:flex;gap:6px;margin-bottom:8px}
.verdict-extra{font-size:12px;color:#b45309;margin-bottom:8px}
.tbl{width:100%;border-collapse:collapse;font-size:12.5px}
.tbl th{text-align:left;color:#64748b;font-weight:600;border-bottom:2px solid #e2e8f0;padding:6px 8px}
.tbl td{border-bottom:1px solid #eef2f7;padding:6px 8px;vertical-align:top}
.mono{font-family:Consolas,"Courier New",monospace;font-size:12px}
.foot{margin-top:18px;color:#94a3b8;font-size:12px;text-align:center}
"""

_JS = """
document.querySelectorAll('.tab').forEach(function(btn){
  btn.addEventListener('click',function(){
    document.querySelectorAll('.tab').forEach(function(b){b.classList.remove('active');});
    document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('active');});
    btn.classList.add('active');
    document.getElementById(btn.dataset.panel).classList.add('active');
  });
});
"""
