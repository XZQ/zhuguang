#!/usr/bin/env python3
"""店巡 Agent · 端到端 Demo(三场景全跑)。

跑通注入的三类异常完整闭环,输出两种形态:
  1. 终端彩色流程(各 Agent 专属配色 + 状态流转)
  2. HTML 复盘报告(demo/report.html,浏览器打开看,可截图交评审)

运行: python3 demo/run_demo.py
无需 Docker/真实 AgentTeams/LLM,纯 Python 复现编排逻辑。
"""

from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dianxun.agents import Orchestrator
from dianxun import trace, console
from dianxun import report as report_mod
from dianxun.knowledge import all_entries


def main() -> int:
    orch = Orchestrator()
    tasks_meta: list[dict] = []

    # ===== 场景 1:冷柜超温(S03/S07)=====
    console.banner("场景 1 · 冷柜超温闭环 — S03/S07")
    r1 = orch.run_task("TASK-COLDCHAIN",
                       scope={"store_ids": ["S03", "S07"], "data_sources": ["iot"]},
                       trigger="event")
    tasks_meta.append({"title": "冷柜超温 S03/S07", "report": r1, "ctx": _ctx_snap(orch, "TASK-COLDCHAIN")})

    # ===== 场景 2:缺货(S05)=====
    console.banner("场景 2 · 缺货闭环 — S05")
    r2 = orch.run_task("TASK-STOCKOUT",
                       scope={"store_ids": ["S05"], "data_sources": ["wms"]},
                       trigger="scheduled")
    tasks_meta.append({"title": "缺货 S05", "report": r2, "ctx": _ctx_snap(orch, "TASK-STOCKOUT")})

    # ===== 场景 3:价签错误(S08)=====
    console.banner("场景 3 · 价签错误闭环 — S08")
    r3 = orch.run_task("TASK-PRICE-TAG",
                       scope={"store_ids": ["S08"], "data_sources": ["price"]},
                       trigger="scheduled")
    tasks_meta.append({"title": "价签错误 S08", "report": r3, "ctx": _ctx_snap(orch, "TASK-PRICE-TAG")})

    # ===== 汇总 =====
    console.banner("全场景汇总 · Trace + 知识飞轮")
    for name, rep in [("冷柜超温", r1), ("缺货", r2), ("价签错误", r3)]:
        if isinstance(rep, dict) and rep.get("result") == "no_anomaly":
            console.detail(f"[{name}] 无异常")
            continue
        tid = rep.get("trace_id", "")
        console.section(f"[{name}] trace={tid}")
        print(trace.trace_summary(tid))
        ke = rep.get("knowledge_entries", [])
        console.detail(f"知识沉淀 {len(ke)} 条:" +
                       (" / ".join(f"{k['title']}({k['status']})" for k in ke) if ke else " 无"))

    kb = all_entries()
    console.section(f"📚 知识库累计 {len(kb)} 条经验(飞轮资产)")
    for e in kb[:5]:
        console.detail(f"• {e['title']} (conf={e['confidence']})")

    # ===== 生成 HTML 报告 =====
    out = Path(__file__).resolve().parents[1] / "demo" / "report.html"
    report_mod.render_report(tasks_meta, kb, out)
    console.ok(f"\n✅ 三场景端到端 Demo 跑通完成")
    console.section("复盘报告已生成")
    console.detail(f"📄 {out}")
    console.detail(f"   浏览器打开查看(可截图交评审)")
    return 0


def _ctx_snap(orch: Orchestrator, task_id: str) -> dict:
    """取任务上下文快照(供 HTML 报告渲染)。"""
    try:
        return orch.bus.get(task_id).snapshot()
    except KeyError:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
