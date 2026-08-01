"""S7. review-report 复盘报告与知识沉淀(经验飞轮引擎)。

九要素(详见 skills/review-report.md):
  用途    对已闭环事件生成复盘报告,沉淀为知识条目/Skill 更新建议
  输入    anomaly_id(s), closed_events[], knowledge_base_schema
  输出    ReviewReport{timeline, root_cause, actions_taken, validation, lessons_learned, knowledge_entries[]}
  安全    报告仅总部可见;知识入库前过质量门(去重/格式);敏感信息自动脱敏
  失败    Trace 不完整→标"部分证据,可信度降级";知识置信度低→标待人工确认,不直进正式库
  协同    稽核 Auditor 调用;写回知识库→下次诊断 RAG 命中→飞轮闭合

被谁调用:稽核 Auditor Agent
关键:这是"越巡越准"飞轮的引擎,把执行经验沉淀为可复用知识
"""

from __future__ import annotations
import uuid
from typing import Any

from .. import trace
from ..knowledge import store as _kb


def review_report(task_ctx: dict, trace_id: str | None = None) -> dict:
    """对已闭环的任务上下文生成复盘报告 + 沉淀知识。

    Args:
        task_ctx: TaskContext.snapshot() 的输出(含 anomalies/root_causes/actions/validation)
        trace_id: 关联 trace
    """
    tid = trace_id or task_ctx.get("trace_id", trace.new_trace_id())
    task_id = task_ctx.get("task_id", "unknown")
    with trace.span("review-report", "skill", tid, input={"task_id": task_id}) as sp:
        # 从 trace 拉时间线
        spans = trace.query_trace(tid)
        timeline = [{
            "step": i + 1, "name": s["name"], "kind": s["kind"],
            "status": s["status"], "duration_ms": s["end_ms"] - s["start_ms"],
        } for i, s in enumerate(spans)]

        root_cause = task_ctx.get("root_causes", [{}])[0].get("hypothesis", "—") \
            if task_ctx.get("root_causes") else "—"
        actions = task_ctx.get("actions", [])
        validation = task_ctx.get("validation", {}) or {}

        # 经验教训
        lessons = _extract_lessons(task_ctx, root_cause, validation)

        # 沉淀知识条目(过质量门:去重/置信度)
        knowledge_entries = []
        for a in task_ctx.get("anomalies", []):
            entry = {
                "title": f"{a.get('type')}处置经验·{a.get('store_id')}",
                "body": f"根因:{root_cause};处置:{[x.get('type') for x in actions]};"
                        f"验证:{validation.get('result', '—')}",
                "tags": [a.get("type", "通用"), a.get("store_id", "")],
                "confidence": min(
                    (task_ctx.get("root_causes", [{}])[0].get("confidence", 0.5) if task_ctx.get("root_causes") else 0.5),
                    validation.get("confidence", 0.8),
                ),
            }
            # 低置信度标待人工,不入正式库
            if entry["confidence"] < 0.6:
                entry["status"] = "待人工确认"
            else:
                entry["status"] = "已入库"
                _kb.add(entry["title"], entry["body"], entry["tags"], entry["confidence"], tid)
            knowledge_entries.append(entry)

        # Skill 更新建议
        skill_suggestions = _skill_update_suggestions(task_ctx, validation)

        report = {
            "report_id": "rv_" + uuid.uuid4().hex[:10],
            "task_id": task_id, "trace_id": tid,
            "timeline": timeline,
            "root_cause": root_cause,
            "actions_taken": actions,
            "validation_results": validation,
            "lessons_learned": lessons,
            "knowledge_entries": knowledge_entries,
            "skill_update_suggestions": skill_suggestions,
            "closed_at": task_ctx.get("transitions", [{}])[-1].get("at", "—"),
        }
        sp.output = {"knowledge_count": len(knowledge_entries),
                     "suggestions": len(skill_suggestions)}
        return report


def _extract_lessons(ctx: dict, root_cause: str, validation: dict) -> list[str]:
    """从闭环结果提炼经验教训。"""
    lessons = []
    v = validation.get("result", "")
    if v == "resolved":
        lessons.append(f"本次处置有效:{root_cause} → 已恢复验证通过")
    elif v == "failed":
        lessons.append(f"本次处置未生效,根因假设可能不准确:{root_cause}")
    # 按异常类型总结
    for a in ctx.get("anomalies", []):
        t = a.get("type")
        if t == "冷柜超温":
            lessons.append("冷柜超温应优先排除环境因素(跨店对标),再判断设备故障")
        elif t == "缺货":
            lessons.append("缺货需检查补货周期与供应商稳定性,安全库存系数可动态调整")
        elif t == "价签不一致":
            lessons.append("价签错误高频店应缩短价签巡检周期,促销上线前强制预检")
    return list(dict.fromkeys(lessons))  # 去重保序


def _skill_update_suggestions(ctx: dict, validation: dict) -> list[dict]:
    """基于复盘结果给出 Skill 迭代建议(飞轮)。"""
    suggestions = []
    # 误报/漏报复盘 → 调阈值
    if validation.get("result") == "false_positive":
        suggestions.append({
            "skill": "anomaly-detect", "action": "上调置信度阈值",
            "reason": "本次为误报,当前阈值过于敏感",
        })
    # 处置未生效 → 修订根因假设
    if validation.get("result") == "failed":
        suggestions.append({
            "skill": "rootcause-drilldown", "action": "补充候选假设",
            "reason": "首假设根因未验证通过,需扩充假设空间",
        })
    return suggestions
