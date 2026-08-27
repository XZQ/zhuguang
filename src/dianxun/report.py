"""复盘报告可视化 v2 — Data-Dense Dashboard 设计系统。

基于 ui-ux-pro-max skill 的设计智能:
- Style: Data-Dense Dashboard(多图表/KPI卡/网格/最大化数据可见性)
- Color: Primary #1E40AF(数据蓝) + CTA #F59E0B(琥珀高亮) + bg #F8FAFC
- Type: Inter(标题/正文) + Fira Code(数据/代码/时间戳)
- Icons: Lucide SVG(不用 emoji)
- Charts: 横向 Bar Chart 对标,带阈值线
- Interaction: hover tooltip / 行高亮 / 平滑过渡 150-300ms
- A11y: 对比度 4.5:1, prefers-reduced-motion, 键盘可达
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any


def render_report(tasks: list[dict], kb_entries: list[dict], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_doc(tasks, kb_entries), encoding="utf-8")
    return out_path


def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


# 8 步闭环(赛题 1.3)
_STEPS = [
    ("任务输入", "Sentry", "log-in"),
    ("任务拆解", "Orchestrator", "split"),
    ("上下文传递", "ContextBus", "share-2"),
    ("工具调用", "Executor", "wrench"),
    ("结果验证", "Auditor", "check-circle"),
    ("证据沉淀", "Trace", "database"),
    ("审批与回滚", "Approval", "shield-check"),
    ("经验沉淀", "Auditor", "sparkles"),
]


def _icon(name: str, size: int = 16) -> str:
    """Lucide SVG 图标(内联,无外部依赖)。"""
    paths = {
        "log-in": '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/>',
        "split": '<polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/>',
        "share-2": '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.6" y1="13.5" x2="15.4" y2="17.5"/><line x1="15.4" y1="6.5" x2="8.6" y2="10.5"/>',
        "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-7.9 7.9l-6.9 6.9a2 2 0 0 1-2.8-2.8l6.9-6.9a6 6 0 0 1 7.9-7.9l-3.8 3.8z"/>',
        "check-circle": '<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><polyline points="22 4 12 14.0 9 11"/>',
        "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.7-4 3-9 3s-9-1.3-9-3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5"/>',
        "shield-check": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/>',
        "sparkles": '<path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/>',
        "activity": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
        "alert-triangle": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.0" y2="17"/>',
        "thermometer": '<path d="M14 14.8V4a2 2 0 0 0-4 0v10.8a4 4 0 1 0 4 0z"/>',
        "package": '<line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.3 7 12 12 20.7 7"/><line x1="12" y1="22" x2="12" y2="12"/>',
        "tag": '<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0l-7.2-7.2a2 2 0 0 1-.6-1.4V4a2 2 0 0 1 2-2h7.6a2 2 0 0 1 1.4.6l7.2 7.2a2 2 0 0 1 0 2.8z"/><circle cx="7" cy="7" r="1.5"/>',
        "trending-down": '<polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/>',
        "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
        "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    }
    p = paths.get(name, "")
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="ico">{p}</svg>'


def _doc(tasks: list[dict], kb: list[dict]) -> str:
    gen = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_spans = sum(len(t["report"].get("timeline", [])) for t in tasks)
    total_kb = len(kb)
    return (
        f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>店巡 Agent · 闭环复盘报告</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>{_CSS}</style></head><body>
<div class="container">
{_header(gen, len(tasks), total_spans, total_kb, tasks)}
{_flow()}
{_kpis(tasks)}
"""
        + "\n".join(_task_section(i, t) for i, t in enumerate(tasks, 1))
        + f"""
{_knowledge(kb)}
<footer><p>店巡 Agent · GOAI Agent Infra 赛道</p><p class="muted">经验飞轮驱动「越巡越准」· Powered by Data-Dense Dashboard Design System</p></footer>
</div></body></html>"""
    )


def _header(gen, n_tasks, n_spans, n_kb, tasks) -> str:
    return f"""
<header class="hero">
  <div class="hero-mark">{_icon("activity", 22)}<span>DIANXUN</span></div>
  <h1>店巡 Agent · 端到端闭环复盘报告</h1>
  <p class="sub">连锁便利店多店异常闭环巡检系统 · AgentTeams 协同基座</p>
  <div class="hero-meta">
    <span>{_icon("clock", 13)} {gen}</span>
    <span>{_icon("layers", 13)} {n_tasks} 任务</span>
    <span>{_icon("activity", 13)} {n_spans} Trace spans</span>
    <span>{_icon("sparkles", 13)} {n_kb} 知识沉淀</span>
  </div>
</header>"""


def _flow() -> str:
    items = []
    for i, (name, actor, ic) in enumerate(_STEPS, 1):
        items.append(
            f'<div class="step" tabindex="0"><div class="step-n">{i}</div>'
            f'<div class="step-ic">{_icon(ic, 18)}</div>'
            f'<div class="step-name">{name}</div>'
            f'<div class="step-agent">{actor}</div></div>'
        )
        if i < 8:
            items.append('<div class="step-arrow">›</div>')
    return f'<section><h2>{_icon("layers", 18)} 8 步端到端闭环 <span class="tag-ref">赛题 1.3</span></h2><div class="flow">{" ".join(items)}</div><p class="hint">验证失败 → reopened → 二次诊断处置(状态机分支)</p></section>'


def _kpis(tasks) -> str:
    sev = {"严重": 0, "高": 0, "中": 0, "低": 0}
    resolved = 0
    for t in tasks:
        for a in t["ctx"].get("anomalies", []):
            sev[a.get("severity", "低")] = sev.get(a.get("severity", "低"), 0) + 1
        resolved += len(
            [
                1
                for v in (t["ctx"].get("validation", {}) or {}).get("by_anomaly", {}).values()
                if v.get("result") == "resolved"
            ]
        )
    cards = [
        ("闭环任务", len(tasks), "layers", "var(--primary)"),
        ("处置异常", sum(sev.values()), "activity", "var(--info)"),
        ("高危/严重", sev.get("严重", 0) + sev.get("高", 0), "alert-triangle", "var(--danger)"),
        ("已验证恢复", resolved, "check-circle", "var(--success)"),
    ]
    grid = "".join(
        f'<div class="kpi"><div class="kpi-ic" style="color:{c}">{_icon(ic, 22)}</div>'
        f'<div class="kpi-num" style="color:{c}">{v}</div><div class="kpi-lbl">{lbl}</div></div>'
        for lbl, v, ic, c in cards
    )
    return f'<section><h2>{_icon("activity", 18)} 总览指标</h2><div class="kpi-grid">{grid}</div></section>'


def _task_section(idx: int, t: dict) -> str:
    title = _esc(t["title"])
    report = t["report"]
    ctx = t["ctx"]
    tid = _esc(ctx.get("trace_id", ""))
    state = _esc(ctx.get("state", ""))
    parts = [
        f'<section class="task"><div class="task-hd"><h2><span class="b-num">{idx:02d}</span> {title}</h2>'
        f'<span class="badge badge-{state}">{state}</span></div>'
        f'<div class="task-meta">{_icon("clock", 12)} trace <code>{tid}</code></div>'
    ]

    # 异常表
    anoms = ctx.get("anomalies", [])
    if anoms:
        rows = "".join(
            f"<tr><td><code>{_esc(a.get('store_id'))}</code></td>"
            f"<td>{_icon(_anom_icon(a.get('type', '')), 14)} {_esc(a.get('type'))}</td>"
            f'<td><span class="sev sev-{_sev_class(a.get("severity"))}">{_esc(a.get("severity"))}</span></td>'
            f'<td><div class="conf-bar"><div style="width:{int(float(a.get("confidence", 0)) * 100)}%"></div></div><td class="num">{a.get("confidence")}</td>'
            f'<td class="mono">{_esc(a.get("matched_rule"))}</td></tr>'
            for a in anoms
        )
        parts.append(
            f'<h3>{_icon("alert-triangle", 15)} 检出异常 <span class="cnt">{len(anoms)}</span></h3>'
            f'<div class="tbl-wrap"><table class="tbl"><thead><tr>'
            '<th>门店</th><th>类型</th><th>严重度</th><th colspan="2">置信度</th><th>命中规则</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div>"
        )

    # 跨店对标
    rcs = ctx.get("root_causes", [])
    bench_data = [
        (
            rc.get("store_id", ""),
            rc.get("contributing_factors", {}).get("max_temp", 0),
            rc.get("confidence", 0),
        )
        for rc in rcs
        if "max_temp" in rc.get("contributing_factors", {})
    ]
    if bench_data:
        parts.append(_bench(bench_data))

    # 根因
    if rcs:
        rc0 = rcs[0]
        cf = rc0.get("contributing_factors", {})
        parts.append(
            f'<div class="rootcause"><div class="rc-hd">{_icon("trending-down", 16)} 根因结论</div>'
            f'<div class="rc-hyp">{_esc(rc0.get("hypothesis", ""))} '
            f'<span class="conf-pill">置信度 {rc0.get("confidence")}</span></div>'
            f'<div class="rc-ctx">对标结论: {_esc(cf.get("benchmark_conclusion", "—"))} · 关联临期 SKU: {_esc(cf.get("related_near_expiry_skus", []) or "无")}</div>'
            f'<div class="rc-plan">下一步 → {_esc(rc0.get("check_plan", {}).get("next_actions", []))}</div></div>'
        )

    # 处置动作
    actions = report.get("actions_taken", []) or ctx.get("actions", [])
    if actions:
        aitems = "".join(
            f'<div class="act"><span class="act-ic {"ok" if a.get("executed") else "warn"}">{_icon("wrench", 14)}</span>'
            f'<span class="act-tag">{_esc(a.get("type", "?"))}</span>'
            f'<span class="act-lbl">{_esc(a.get("anomaly_type", ""))}</span>'
            f'<span class="act-st {"ok" if a.get("executed") else "warn"}">{"已执行" if a.get("executed") else "待审批"}</span></div>'
            for a in actions[:8]
        )
        parts.append(
            f'<h3>{_icon("wrench", 15)} 处置动作 <span class="cnt">{len(actions)}</span></h3><div class="acts">{aitems}</div>'
        )

    # Trace
    timeline = report.get("timeline", [])
    if timeline:
        max_ms = max((s.get("duration_ms", 1) for s in timeline), default=1) or 1
        titems = "".join(
            f'<div class="tr" title="{_esc(s.get("name", ""))} · {s.get("duration_ms", 0)}ms">'
            f'<span class="tr-n">{s.get("step")}</span>'
            f'<span class="tr-k k-{_esc(s.get("kind", ""))}">{_esc(s.get("kind", ""))}</span>'
            f'<span class="tr-name">{_esc(s.get("name", ""))}</span>'
            f'<span class="tr-bar"><span class="tr-fill" style="width:{max(8, int(s.get("duration_ms", 0) / max_ms * 100))}%"></span></span>'
            f'<span class="tr-ms {"ok" if s.get("status") == "ok" else "err"}">{"✓" if s.get("status") == "ok" else "✗"} {s.get("duration_ms", 0)}ms</span></div>'
            for s in timeline
        )
        parts.append(
            f'<h3>{_icon("database", 15)} 全链路 Trace <span class="cnt">{len(timeline)} spans</span></h3><div class="trace">{titems}</div>'
        )

    parts.append("</section>")
    return "".join(parts)


def _bench(data) -> str:
    """跨店对标:目标店温度 vs 5℃ 阈值。横向 bar。"""
    rows = []
    threshold = 5.0
    max_v = max((d[1] for d in data), default=threshold)
    scale_max = max(max_v, threshold) * 1.15
    for sid, temp, conf in data:
        pct = temp / scale_max * 100
        over = temp > threshold
        th_pct = threshold / scale_max * 100
        bar = (
            f'<div class="bench-row"><div class="bench-lbl"><code>{_esc(sid)}</code></div>'
            f'<div class="bench-track"><div class="bench-th" style="left:{th_pct}%"></div>'
            f'<div class="bench-bar {"over" if over else ""}" style="width:{pct}%">'
            f'<span class="bench-val">{temp}℃</span></div></div>'
            f'<div class="bench-conf">conf {conf}</div></div>'
        )
        rows.append(bar)
    return (
        f"<h3>{_icon('thermometer', 15)} 跨店对标 · 温度异常(阈值 5℃)</h3>"
        f'<div class="bench">{" ".join(rows)}</div>'
        f'<p class="hint">目标店温度显著高于阈值线 → 单店孤立异常 → 排除环境因素定位设备故障</p>'
    )


def _knowledge(kb: list[dict]) -> str:
    if not kb:
        return f'<section><h2>{_icon("sparkles", 18)} 知识飞轮</h2><p class="empty">暂无沉淀</p></section>'
    items = []
    for e in kb:
        conf = e.get("confidence", 0)
        tags = "".join(f'<span class="tag">{_esc(t)}</span>' for t in e.get("tags", [])[:3])
        items.append(
            f'<div class="kb-card"><div class="kb-top"><div class="kb-title">{_esc(e.get("title", ""))}</div>'
            f'<div class="kb-conf">{conf}</div></div>'
            f'<div class="kb-tags">{tags}</div>'
            f'<div class="kb-conf-bar"><div style="width:{int(conf * 100)}%"></div></div>'
            f'<div class="kb-body">{_esc(e.get("body", "")[:110])}…</div></div>'
        )
    return (
        f"<section><h2>{_icon('sparkles', 18)} 知识飞轮 · 累计 {len(kb)} 条经验</h2>"
        f'<div class="kb-grid">{"".join(items)}</div>'
        f'<p class="hint">下次诊断 Agent 经 RAG 检索命中 → 诊断更准 → 越巡越准</p></section>'
    )


def _anom_icon(t: str) -> str:
    return {
        "冷柜超温": "thermometer",
        "缺货": "package",
        "低库存": "package",
        "价签不一致": "tag",
        "临期": "clock",
    }.get(t, "alert-triangle")


def _sev_class(s) -> str:
    return {"严重": "crit", "高": "high", "中": "mid", "低": "low"}.get(s or "", "low")


_CSS = """
:root{
  --primary:#1E40AF; --primary-lt:#3B82F6; --info:#0891B2; --success:#059669;
  --warn:#D97706; --danger:#DC2626; --amber:#F59E0B; --purple:#7C3AED;
  --bg:#F8FAFC; --surface:#FFFFFF; --text:#0F172A; --text-2:#475569; --muted:#94A3B8;
  --border:#E2E8F0; --border-2:#CBD5E1;
  --radius:10px; --radius-sm:6px;
  --shadow:0 1px 3px rgba(15,23,42,.06),0 1px 2px rgba(15,23,42,.04);
  --shadow-md:0 4px 12px rgba(15,23,42,.08);
  --sans:'Inter',-apple-system,'PingFang SC',sans-serif;
  --mono:'Fira Code',ui-monospace,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--sans);background:var(--bg);color:var(--text);line-height:1.6;-webkit-font-smoothing:antialiased}
.container{max-width:1180px;margin:0 auto;padding:40px 28px 60px}
code{font-family:var(--mono);font-size:.88em;background:#EFF6FF;color:var(--primary);padding:1px 6px;border-radius:4px}
.mono{font-family:var(--mono);font-size:12px;color:var(--text-2)}
.num{font-family:var(--mono)}
.ico{vertical-align:-2px}
/* hero */
.hero{background:linear-gradient(135deg,#0F172A 0%,#1E3A8A 100%);color:#fff;padding:40px 36px;border-radius:16px;margin-bottom:28px;box-shadow:var(--shadow-md);position:relative;overflow:hidden}
.hero::after{content:"";position:absolute;right:-40px;top:-40px;width:240px;height:240px;background:radial-gradient(circle,rgba(245,158,11,.18),transparent 70%)}
.hero-mark{display:flex;align-items:center;gap:8px;font-weight:700;letter-spacing:.18em;font-size:12px;color:var(--amber);margin-bottom:14px}
.hero h1{font-size:32px;font-weight:700;letter-spacing:-.02em;line-height:1.15}
.hero .sub{color:rgba(255,255,255,.72);margin-top:6px;font-size:14px}
.hero-meta{display:flex;flex-wrap:wrap;gap:18px;margin-top:18px;font-size:13px;color:rgba(255,255,255,.85)}
.hero-meta span{display:inline-flex;align-items:center;gap:5px}
/* section */
section{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px 26px;margin-bottom:18px;box-shadow:var(--shadow)}
h2{font-size:18px;font-weight:600;display:flex;align-items:center;gap:8px;margin-bottom:18px}
h2 .ico{color:var(--primary)}
h3{font-size:14px;font-weight:600;color:var(--text-2);margin:20px 0 12px;display:flex;align-items:center;gap:6px}
.tag-ref{font-size:11px;font-weight:500;background:#EFF6FF;color:var(--primary);padding:2px 8px;border-radius:20px}
.cnt{font-size:12px;font-weight:500;color:var(--primary);background:#EFF6FF;padding:2px 8px;border-radius:20px}
.hint{font-size:12px;color:var(--muted);margin-top:10px}
/* flow */
.flow{display:flex;align-items:stretch;flex-wrap:wrap;gap:4px}
.step{flex:1;min-width:96px;background:#F8FAFC;border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px 8px;text-align:center;transition:all .2s;cursor:default}
.step:hover,.step:focus{border-color:var(--primary);background:#EFF6FF;transform:translateY(-2px);box-shadow:var(--shadow-md);outline:none}
.step-n{width:22px;height:22px;background:var(--primary);color:#fff;border-radius:50%;font-size:11px;font-weight:600;display:flex;align-items:center;justify-content:center;margin:0 auto 6px}
.step-ic{color:var(--primary);margin-bottom:4px}.step-ic .ico{width:20px;height:20px}
.step-name{font-size:13px;font-weight:600}
.step-agent{font-size:11px;color:var(--muted);margin-top:2px}
.step-arrow{display:flex;align-items:center;color:var(--border-2);font-size:22px;font-weight:300}
/* kpi */
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.kpi{background:#F8FAFC;border:1px solid var(--border);border-radius:var(--radius-sm);padding:18px 16px;display:flex;flex-direction:column;align-items:flex-start;gap:4px;transition:all .2s}
.kpi:hover{box-shadow:var(--shadow-md);transform:translateY(-2px)}
.kpi-ic{margin-bottom:4px}
.kpi-num{font-size:34px;font-weight:700;line-height:1;letter-spacing:-.02em}
.kpi-lbl{font-size:13px;color:var(--text-2)}
/* task */
.task-hd{display:flex;align-items:center;justify-content:space-between;gap:12px}
.task-hd h2{margin-bottom:0}
.b-num{font-family:var(--mono);color:var(--amber);font-weight:700}
.task-meta{font-size:12px;color:var(--muted);margin:6px 0 4px;display:flex;align-items:center;gap:6px}
.badge{font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;text-transform:uppercase;letter-spacing:.05em}
.badge-closed{background:#DCFCE7;color:#15803D}.badge-reviewing{background:#FEF3C7;color:#B45309}
.badge-verifying{background:#E0F2FE;color:#0369A1}.badge-reopened{background:#FEE2E2;color:#B91C1C}
/* table */
.tbl-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:var(--radius-sm)}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl th{background:#F8FAFC;text-align:left;padding:10px 12px;font-weight:600;color:var(--text-2);border-bottom:2px solid var(--border-2);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.tbl td{padding:9px 12px;border-bottom:1px solid var(--border)}
.tbl tbody tr{transition:background .15s}
.tbl tbody tr:hover{background:#F8FAFC}
.tbl td code{font-size:12px}
.sev{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600;color:#fff}
.sev-crit{background:var(--danger)}.sev-high{background:#EA580C}.sev-mid{background:var(--warn)}.sev-low{background:#65A30D}
.conf-bar{width:60px;height:6px;background:#E2E8F0;border-radius:3px;overflow:hidden;display:inline-block;vertical-align:middle}
.conf-bar div{height:100%;background:var(--primary-lt);border-radius:3px}
/* bench */
.bench{background:#F8FAFC;border:1px solid var(--border);border-radius:var(--radius-sm);padding:16px}
.bench-row{display:grid;grid-template-columns:60px 1fr 70px;gap:12px;align-items:center;padding:8px 0}
.bench-track{position:relative;height:26px;background:#E2E8F0;border-radius:6px;overflow:visible}
.bench-th{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--danger);z-index:2}
.bench-th::after{content:"5℃";position:absolute;top:-16px;left:-10px;font-size:10px;color:var(--danger);font-weight:600}
.bench-bar{height:100%;background:linear-gradient(90deg,var(--primary),var(--primary-lt));border-radius:6px;display:flex;align-items:center;justify-content:flex-end;padding-right:8px;transition:width .4s;position:relative;z-index:1}
.bench-bar.over{background:linear-gradient(90deg,var(--danger),#F87171)}
.bench-val{color:#fff;font-size:12px;font-weight:700;font-family:var(--mono)}
.bench-conf{font-size:11px;color:var(--muted);font-family:var(--mono);text-align:right}
/* rootcause */
.rootcause{background:linear-gradient(135deg,#FFFBEB,#FEF3C7);border:1px solid #FDE68A;border-left:4px solid var(--amber);border-radius:var(--radius-sm);padding:14px 18px;margin-top:14px}
.rc-hd{font-weight:600;font-size:13px;color:#92400E;display:flex;align-items:center;gap:6px;margin-bottom:6px}
.rc-hyp{font-size:15px;font-weight:600;color:var(--text)}
.conf-pill{font-size:12px;font-weight:600;color:var(--amber);background:#fff;padding:2px 10px;border-radius:20px;border:1px solid #FDE68A;margin-left:6px}
.rc-ctx{font-size:12px;color:var(--text-2);margin-top:6px}
.rc-plan{font-size:12px;color:#92400E;margin-top:6px;font-family:var(--mono)}
/* actions */
.acts{display:flex;flex-direction:column;gap:6px}
.act{display:flex;align-items:center;gap:10px;padding:8px 12px;background:#F8FAFC;border:1px solid var(--border);border-radius:var(--radius-sm);transition:all .15s}
.act:hover{border-color:var(--primary-lt);background:#fff}
.act-ic{width:24px;height:24px;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#fff}
.act-ic.ok{background:var(--success)}.act-ic.warn{background:var(--warn)}
.act-tag{font-family:var(--mono);font-size:11px;background:#EFF6FF;color:var(--primary);padding:2px 8px;border-radius:4px}
.act-lbl{font-size:13px;color:var(--text);flex:1}
.act-st{font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px}
.act-st.ok{background:#DCFCE7;color:#15803D}.act-st.warn{background:#FEF3C7;color:#B45309}
/* trace */
.trace{background:#0F172A;border-radius:var(--radius-sm);padding:14px;font-family:var(--mono)}
.tr{display:grid;grid-template-columns:28px 56px 1fr 1fr 90px;gap:10px;align-items:center;padding:5px 6px;border-bottom:1px solid rgba(255,255,255,.06);transition:background .15s}
.tr:hover{background:rgba(255,255,255,.05)}
.tr-n{color:var(--muted);font-size:11px}
.tr-k{font-size:9px;padding:2px 6px;border-radius:3px;color:#fff;text-align:center;text-transform:uppercase;letter-spacing:.04em;font-weight:600}
.k-skill{background:var(--primary-lt)}.k-agent{background:var(--purple)}.k-mcp{background:var(--info)}.k-llm{background:var(--success)}
.tr-name{color:#E2E8F0;font-size:12px}
.tr-bar{height:5px;background:rgba(255,255,255,.1);border-radius:3px;overflow:hidden}
.tr-fill{height:100%;background:linear-gradient(90deg,var(--primary-lt),var(--info));border-radius:3px}
.tr-ms{font-size:11px;text-align:right}
.tr-ms.ok{color:#34D399}.tr-ms.err{color:#F87171}
/* kb */
.kb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.kb-card{background:#F8FAFC;border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px;transition:all .2s}
.kb-card:hover{box-shadow:var(--shadow-md);transform:translateY(-2px);background:#fff}
.kb-top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.kb-title{font-weight:600;font-size:13px;line-height:1.4}
.kb-conf{font-family:var(--mono);font-size:13px;font-weight:600;color:var(--purple);background:#F5F3FF;padding:2px 8px;border-radius:20px;flex-shrink:0}
.kb-tags{display:flex;gap:4px;margin:8px 0}
.tag{font-size:10px;background:#fff;border:1px solid var(--border);color:var(--text-2);padding:1px 7px;border-radius:20px}
.kb-conf-bar{height:4px;background:#E2E8F0;border-radius:2px;margin-bottom:8px;overflow:hidden}
.kb-conf-bar div{height:100%;background:var(--purple);border-radius:2px}
.kb-body{font-size:12px;color:var(--muted);line-height:1.5}
.empty{color:var(--muted);padding:20px;text-align:center}
footer{text-align:center;color:var(--muted);font-size:12px;margin-top:32px;padding:20px}
footer .muted{font-size:11px;margin-top:4px}
@media(max-width:768px){.kpi-grid{grid-template-columns:repeat(2,1fr)}.flow{gap:2px}.step{min-width:calc(50% - 4px)}.hero h1{font-size:24px}.tr{grid-template-columns:24px 50px 1fr 70px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""
