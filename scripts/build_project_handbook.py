# /// script
# requires-python = ">=3.11"
# dependencies = ["reportlab==4.4.9", "mistune==3.1.3"]
# ///
"""Export the current Markdown and evidence as one illustrated Chinese handbook.

Run with uv run scripts/build_project_handbook.py. On non-Windows hosts provide
--font and --bold-font pointing to Chinese TrueType fonts. Historical PDFs are
read-only inputs to the preservation check, never authoring targets.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import mistune
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/competition/店巡Agent-项目与答辩手册.pdf"
INPUTS = {
    "intro": "docs/competition/项目简介.md",
    "talk": "docs/competition/决赛讲稿与问答.md",
    "tech": "docs/技术说明.md",
    "runtime": "docs/operations/runtime-recovery.md",
    "todo": "docs/待办.md",
    "tests": "docs/测试覆盖矩阵.md",
}
DATA = ["config/project-facts.json", "evidence/m4/ablation.json", "skills/registry.json"]
INK, TEAL, MUTED = "#172B43", "#087F8C", "#586A7D"
PALE, BORDER = "#F2F6FA", "#DCE5EE"
WIDTH, HEIGHT = A4
MARGIN = 47
CONTENT = WIDTH - MARGIN * 2
MD = mistune.create_markdown(renderer="ast", plugins=["table"])
LINKS = {
    "技术说明.md": "architecture",
    "待办.md": "todo",
    "测试覆盖矩阵.md": "evidence",
    "runtime-recovery.md": "recovery",
    "决赛讲稿与问答.md": "script-1",
}


def digest(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def plain(nodes: list[dict]) -> str:
    return "".join(node.get("raw", plain(node.get("children", []))) for node in nodes)


def inline(nodes: list[dict]) -> str:
    chunks = []
    for node in nodes:
        kind = node["type"]
        value = inline(node.get("children", []))
        if kind == "strong":
            chunks.append(f"<b>{value}</b>")
        elif kind == "emphasis":
            chunks.append(value)
        elif kind == "link":
            url = node["attrs"]["url"]
            target = LINKS.get(Path(url.split("#")[0]).name)
            if target:
                chunks.append(f'<link href="#{target}" color="{TEAL}">{value}</link>')
            elif url.startswith(("https://", "http://")):
                chunks.append(f'<link href="{html.escape(url, quote=True)}">{value}</link>')
            else:
                chunks.append(value)
        elif kind == "codespan":
            chunks.append(f'<font color="{TEAL}">{html.escape(node["raw"])}</font>')
        elif kind in ("softbreak", "linebreak"):
            chunks.append(" " if kind == "softbreak" else "<br/>")
        elif "raw" in node:
            chunks.append(html.escape(node["raw"]))
        else:
            chunks.append(value)
    return "".join(chunks)


def section(nodes: list[dict], title: str) -> list[dict]:
    for start, node in enumerate(nodes):
        if node["type"] != "heading" or plain(node["children"]) != title:
            continue
        level = node["attrs"]["level"]
        for end in range(start + 1, len(nodes)):
            other = nodes[end]
            if other["type"] == "heading" and other["attrs"]["level"] <= level:
                return nodes[start + 1 : end]
        return nodes[start + 1 :]
    raise ValueError(f"Missing Markdown section: {title}")


def tables(nodes: list[dict]) -> list[list[list[str]]]:
    result = []
    for node in nodes:
        if node["type"] != "table":
            continue
        head, body = node["children"]
        result.append(
            [[inline(cell["children"]) for cell in head["children"]]]
            + [[inline(cell["children"]) for cell in row["children"]] for row in body["children"]]
        )
    return result


def subsections(nodes: list[dict]) -> list[tuple[str, list[dict]]]:
    return [
        (plain(node["children"]), section(nodes, plain(node["children"])))
        for node in nodes
        if node["type"] == "heading" and node["attrs"]["level"] == 3
    ]


def style(name, size=10, leading=16, **kwargs):
    return ParagraphStyle(
        name,
        fontName="ZG",
        fontSize=size,
        leading=leading,
        textColor=colors.HexColor(INK),
        wordWrap="CJK",
        splitLongWords=True,
        alignment=TA_LEFT,
        spaceAfter=7,
        **kwargs,
    )


def paragraph(text, kind="body"):
    return Paragraph(text, STYLES[kind])


def heading(text):
    return paragraph(html.escape(text), "sub")


def table(rows, fractions=None, compact=False):
    widths = [CONTENT / len(rows[0])] * len(rows[0])
    if fractions:
        widths = [CONTENT * fraction / sum(fractions) for fraction in fractions]
    items = [
        [paragraph(str(cell), "cell_head" if index == 0 else "cell") for cell in row]
        for index, row in enumerate(rows)
    ]
    block = Table(items, colWidths=widths, repeatRows=1, hAlign="LEFT")
    block.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(INK)),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(PALE)]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor(BORDER)),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5 if compact else 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5 if compact else 7),
            ]
        )
    )
    return block


def note(text):
    box = Table([[paragraph(text, "small")]], colWidths=[CONTENT])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALE)),
                ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(TEAL)),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return box


def blocks(nodes):
    result = []
    for node in nodes:
        kind = node["type"]
        if kind in ("paragraph", "block_text"):
            result.append(paragraph(inline(node["children"])))
        elif kind == "heading":
            result.append(heading(plain(node["children"])))
        elif kind == "table":
            rows = tables([node])[0]
            result.extend([table(rows), Spacer(1, 8)])
        elif kind == "list":
            for index, item in enumerate(node["children"], 1):
                prefix = f"{index}. " if node.get("attrs", {}).get("ordered") else "• "
                children = item["children"]
                for child in children:
                    if child["type"] in ("paragraph", "block_text"):
                        result.append(paragraph(prefix + inline(child["children"]), "small"))
                        prefix = ""
                    else:
                        result.extend(blocks([child]))
        elif kind == "block_quote":
            result.extend(blocks(node["children"]))
        elif kind == "block_code":
            lines = node["raw"].strip().splitlines()
            code = "<br/>".join(html.escape(line).replace(" ", "&#160;") for line in lines)
            result.append(note(paragraph(code, "code").text))
        elif kind not in ("blank_line", "thematic_break"):
            raise ValueError(f"Unsupported Markdown block: {kind}")
    return result


def diagram():
    drawing = Drawing(CONTENT, 186)

    def box(x, y, width, title, subtitle, fill=PALE):
        drawing.add(
            Rect(
                x,
                y,
                width,
                48,
                rx=6,
                ry=6,
                fillColor=colors.HexColor(fill),
                strokeColor=colors.HexColor(BORDER),
            )
        )
        drawing.add(
            String(
                x + width / 2,
                y + 29,
                title,
                fontName="ZG-Bold",
                fontSize=10,
                textAnchor="middle",
                fillColor=colors.HexColor(INK),
            )
        )
        drawing.add(
            String(
                x + width / 2,
                y + 12,
                subtitle,
                fontName="ZG",
                fontSize=8.2,
                textAnchor="middle",
                fillColor=colors.HexColor(MUTED),
            )
        )

    box(0, 133, CONTENT / 2 - 8, "本地确定性运行", "LocalDemoAdapter / ScenarioEngine")
    box(
        CONTENT / 2 + 8,
        133,
        CONTENT / 2 - 8,
        "目标 AgentTeams Worker",
        "/runtime 接口；动态协作外部待验",
    )
    for x in [CONTENT / 4, CONTENT * 3 / 4]:
        drawing.add(Line(x, 133, x, 117, strokeColor=colors.HexColor(TEAL), strokeWidth=1.2))
        drawing.add(
            Line(x, 117, CONTENT / 2, 117, strokeColor=colors.HexColor(TEAL), strokeWidth=1.2)
        )
    drawing.add(Line(CONTENT / 2, 117, CONTENT / 2, 109, strokeColor=colors.HexColor(TEAL)))
    box(46, 61, CONTENT - 92, "IncidentService", "业务状态与终态判断的唯一入口", "#E6F3F3")
    drawing.add(Line(CONTENT / 2, 61, CONTENT / 2, 49, strokeColor=colors.HexColor(TEAL)))
    box(
        0,
        0,
        CONTENT,
        "Policy  /  StateStore  /  MCP 工具",
        "角色与审批、事务与幂等、读写事实与审计",
    )
    return drawing


class Handbook(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if getattr(flowable, "outline_key", None):
            self.canv.bookmarkPage(flowable.outline_key)
            self.canv.addOutlineEntry(flowable.getPlainText(), flowable.outline_key)
            self.sections.append({"title": flowable.getPlainText(), "page": self.page})


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("ZG", 8)
    canvas.setFillColor(colors.HexColor(MUTED))
    canvas.drawString(MARGIN, HEIGHT - 29, "逐光  /  店巡 Agent")
    canvas.drawRightString(WIDTH - MARGIN, HEIGHT - 29, "项目与答辩手册")
    canvas.setStrokeColor(colors.HexColor(BORDER))
    canvas.line(MARGIN, 37, WIDTH - MARGIN, 37)
    canvas.drawString(MARGIN, 24, f"资料版本 {doc.edition}  ·  当前工作区导出")
    canvas.drawRightString(WIDTH - MARGIN, 24, f"{doc.page:02}")
    canvas.restoreState()


def make_story(sources, facts, ablation, edition, commit, source_hashes):
    story = []
    evaluation = facts["implementation"]["m4_evaluation"]
    talk = sources["talk"]
    tech = sources["tech"]
    runtime = sources["runtime"]

    def chapter(key, title, subtitle):
        if story:
            story.append(PageBreak())
        title_block = paragraph(title, "title")
        title_block.outline_key = key
        story.extend([title_block, paragraph(subtitle, "caption"), Spacer(1, 9)])

    chapter("overview", "项目与答辩手册", f"店巡 Agent  |  逐光队  |  {edition}")
    story.append(note("<b>设备恢复不等于商品安全。事件只有在证据闭环后才能关闭。</b>"))
    story.extend([Spacer(1, 16), heading("项目介绍")])
    story.extend(blocks(section(sources["intro"], "500 字作品简介")))
    story.extend(
        [
            heading("使用这份手册"),
            paragraph(
                "现场速查、架构与契约、恢复与证据、演示操作、逐页讲稿和评委问答合在同一份文件。"
                "正文取自现行 Markdown，数字取自事实源；后续更新源文档后重新导出。"
            ),
            note(
                "代码与本地回归已有证据；真实 AgentTeams、PolarDB、企业接口和门店收益仍待验收。"
                "讲稿中的 VeriAgent 是决赛工作标题，正式作品名仍为店巡 Agent。"
            ),
            Spacer(1, 12),
            paragraph(
                '<link href="#quick">现场速查</link>　'
                '<link href="#architecture">架构</link>　'
                '<link href="#evidence">证据</link>　'
                '<link href="#demo">演示</link>　'
                '<link href="#script-1">讲稿</link>　'
                '<link href="#faq-1">问答</link>　'
                '<link href="#todo">待办</link>　'
                '<link href="#sources">版本来源</link>',
                "small",
            ),
        ]
    )

    chapter("quick", "01  现场速查", "先明确场景、正确终态和证据范围。")
    story.append(
        table(
            [
                ["项目", "当前可使用的口径"],
                ["作品 / 队伍", f"{facts['project_name']} / {facts['team_name']}"],
                ["角色 / 契约", "5 个业务角色、6 个 P0 Skill、12 个 P0 MCP；3 个知识工具可选"],
                [
                    "完整测试",
                    f"{evaluation['full_unittest_count']} 项发现，"
                    f"{evaluation['full_unittest_passed']} 通过，"
                    f"{evaluation['conditional_integration_skipped']} 项 PolarDB 条件跳过",
                ],
                [
                    "记录环境",
                    f"{evaluation['unittest_verified_at']}；Windows / Python 3.12.13 / 本地 SQLite",
                ],
                ["模型", f"目标配置 {facts['agentteams']['default_model']}；本地评测不调用大模型"],
            ],
            [0.22, 0.78],
        )
    )
    story.extend([Spacer(1, 14), heading("六场景的正确结果")])
    story.append(table(tables(section(tech, "数据、场景与证据"))[1], [0.4, 0.6]))
    story.extend(
        [
            Spacer(1, 12),
            note(
                "优先演示 A，再展示 E，F 作为失败处理备用。展示解除停售前后两次核验时使用 B。"
                "动画、配置、工单完成或设备回温，都不能替代真实平台记录或商品安全验收。"
            ),
        ]
    )

    chapter(
        "architecture", "02  架构与协作", "一个业务核心，两种接入方式；五个业务角色分别承担责任。"
    )
    story.extend([diagram(), Spacer(1, 12)])
    story.append(table(tables(section(tech, "架构与身份"))[0], [0.19, 0.37, 0.44], True))
    story.extend([Spacer(1, 10), heading("业务阶段与运行步骤")])
    story.append(table(tables(section(tech, "业务流程与成功条件"))[0], [0.23, 0.42, 0.35], True))

    chapter("contracts", "03  Skill、MCP 与安全", "契约、执行权限和业务前置条件共同约束动作。")
    story.append(table(tables(section(tech, "Skill 契约"))[0], [0.28, 0.12, 0.15, 0.45], True))
    for title, values in [
        ("5 个 P0 查询", facts["p0_mcp"]["queries"]),
        ("7 个 P0 动作", facts["p0_mcp"]["actions"]),
        ("3 个可选知识工具", facts["p1_mcp"]["tools"]),
    ]:
        story.extend([heading(title), paragraph("、".join(values), "small")])
    mcp = section(tech, "MCP 工具与错误语义")
    story.extend(
        [heading("响应与失败处理"), *blocks([n for n in mcp if n["type"] == "paragraph"][-1:])]
    )
    story.append(
        note(
            "查询不完整不能当作成功。Executor 不决定审批；Human 凭证不注入模型。"
            "解除停售需要对应批准与新鲜的 Auditor release_guard，随后还要重查。"
            "幂等与本地事务不能撤销已经发生的真实外部副作用。"
        )
    )

    chapter(
        "recovery",
        "04  运行与故障恢复",
        "服务端执行截止与预算，Worker 的完成声明不能推进业务终态。",
    )
    story.extend(blocks(section(runtime, "启动与任务消费")[:2]))
    story.append(table(tables(section(runtime, "固定预算与状态"))[0], [0.27, 0.73], True))
    story.extend(
        [
            Spacer(1, 10),
            note(
                "已实现：后台巡查、主控监督、硬截止、有效进展、有限重试、健康备用与容量、"
                "等待唤醒、输出恢复、回执核验、人工升级、通知 Outbox 和受控应急汇合。"
                f"恢复专项有 {facts['implementation']['runtime_recovery']['recovery_tests']} "
                "项本地回归。"
            ),
            Spacer(1, 8),
            paragraph(
                "通知 Outbox 尚未连接真实短信、飞书或邮件。应急停售默认关闭，仅在预授权范围启用。"
                "未知回执、预算耗尽和不可重试故障转人工；不得刷新预算、伪造成功检查点或恢复旧租约。",
                "small",
            ),
        ]
    )

    chapter(
        "evidence", "05  评测结果与证据", f"完整回归记录：{evaluation['unittest_verified_at']}。"
    )
    story.append(table(tables(section(sources["tests"], "1. 当前统计"))[0], [0.43, 0.57], True))
    story.extend(
        [
            Spacer(1, 12),
            heading("六场景确定性评测"),
            paragraph(
                f"{evaluation['scenario_passed']}/{evaluation['scenario_count']} 场景通过；"
                f"Top-1、Top-3 均为 {evaluation['top1_hits']}/{evaluation['scenario_count']}；"
                f"Evidence {evaluation['complete_evidence_records']}/"
                f"{evaluation['evidence_records']}；"
                f"Trace {evaluation['covered_trace_phases']}/"
                f"{evaluation['expected_trace_phases']}；"
                f"测试定义的安全违规 {evaluation['safety_violations']} 起。"
            ),
            heading("消融实验：按实际结果解释"),
        ]
    )
    summaries = ablation["summary"]
    story.append(
        table(
            [
                ["设置", "实际观察", "解释边界"],
                [
                    "full",
                    f"{summaries['full']['acceptance_passed']}/6 验收通过",
                    "本系统的固定合成样本",
                ],
                [
                    "no_auditor",
                    f"{summaries['no_auditor']['verification_blocked']}/6 停于 VERIFY/BLOCKED；"
                    f"{summaries['no_auditor']['unsafe_releases']} 不安全放行",
                    "缺少独立验证时保持遏制，其他安全门仍然生效",
                ],
                [
                    "single_agent",
                    f"{summaries['single_agent']['denied_write_attempts']} 次写入被拒",
                    "验证本系统单身份的权限边界",
                ],
                [
                    "rule_only",
                    f"Top-1 {summaries['rule_only']['top1_hits']}/6；"
                    f"{summaries['rule_only']['misrouted_workorders']} 次错派",
                    "替换诊断排序，保留下游防线",
                ],
            ],
            [0.2, 0.39, 0.41],
            True,
        )
    )
    story.extend(
        [
            Spacer(1, 12),
            note(
                "这些结果不证明模型效果、生产准确率或经营收益，"
                "也不支持“去掉 Auditor 导致 5 次错误放行”。"
                "真实 AgentTeams、PolarDB/OSS、企业接口、容器与门店验证分别取证。"
            ),
        ]
    )

    chapter(
        "demo",
        "06  演示与录屏",
        "本地演示开场说明：设备、维修和审批为合成数据，业务状态实际写入本地数据库。",
    )
    demo = section(talk, "2. 演示操作与口播")
    story.append(table(tables(demo)[0], [0.25, 0.39, 0.36], True))
    story.extend([Spacer(1, 10), heading("独立临时数据库复现 A / E / F")])
    replay = section(talk, "6. 本地复现与录屏")
    code = next(node["raw"] for node in replay if node["type"] == "block_code")
    code_html = "<br/>".join(
        html.escape(line).replace(" ", "&#160;") for line in code.strip().splitlines()
    )
    code_box = Table([[paragraph(code_html, "code")]], colWidths=[CONTENT])
    code_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALE)),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER)),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend(
        [
            code_box,
            Spacer(1, 8),
            paragraph(
                "A 为 CLOSED；E 保持 CONTAINED / WAITING_APPROVAL；"
                "F 为本地 reopened / CONTAINED / EXECUTE / BLOCKED。"
                "展示受控解禁用 B；平台录像保留真实委派、身份、租约、"
                "检查点、回执与独立核验，录屏须脱敏。",
                "small",
            ),
        ]
    )

    speech = subsections(section(talk, "1. 逐页讲稿"))
    for index in range(3):
        chapter(
            f"script-{index + 1}",
            f"07  逐页讲稿  {index * 4 + 1:02}-{index * 4 + 4:02}",
            "对应 12 页决赛工作稿。正式陈述、演示与问答时长依组委会通知。",
        )
        for title, nodes in speech[index * 4 : index * 4 + 4]:
            story.append(KeepTogether([heading(title), *blocks(nodes), Spacer(1, 16)]))
        if index == 0:
            story.append(
                note("VeriAgent 为讲稿工作标题；正式名称、PPT 版本和现场时长在交付时统一冻结。")
            )

    questions = subsections(section(talk, "3. 评委问答"))
    questions += subsections(section(talk, "4. 技术问答补充"))
    for index, group in enumerate([questions[:7], questions[7:]]):
        chapter(
            f"faq-{index + 1}",
            f"08  评委问答  {index + 1}/2",
            "先说明当前实现，再给证据与适用边界。",
        )
        for title, nodes in group:
            story.append(KeepTogether([heading(title), *blocks(nodes), Spacer(1, 5)]))

    chapter("todo", "09  当前待办与交付", "本页为导出时快照。唯一维护入口仍是 docs/待办.md。")
    todo = section(sources["todo"], "当前执行清单")
    story.append(table(tables(todo)[0], [0.08, 0.08, 0.15, 0.69], True))
    story.extend(
        [
            Spacer(1, 12),
            note(
                "原待办 01 的有界恢复已完成本地实现；原待办 02 的分析与 36 项验收要求已整理，"
                "业务代码缺口仍需修复；原待办 03 的方案已制定，真实目标平台验收仍待执行。"
            ),
            Spacer(1, 8),
            paragraph(
                "现场需冻结正式时长、材料格式、源码与部署版本、PPT、讲稿和录屏。"
                "新手册完成不等于实际平台、全部材料或正式提交完成。",
                "small",
            ),
        ]
    )

    chapter("sources", "10  版本、来源与复核", "保留可追溯输入，更新正文后显式导出并检查每页。")
    story.append(
        table(
            [
                ["项目", "本次记录"],
                ["资料日期", edition],
                ["源码基线", commit],
                ["内容来源", "当前工作区的现行 Markdown 与结构化事实；包含本轮文档整理"],
                ["测试记录", f"{evaluation['unittest_verified_at']}；详见测试覆盖矩阵"],
                [
                    "源内容摘要",
                    hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest(),
                ],
                ["正式名称", "逐光 / 店巡 Agent；VeriAgent 为决赛工作稿标题"],
            ],
            [0.22, 0.78],
            True,
        )
    )
    story.extend([Spacer(1, 14), heading("权威维护位置")])
    for key, location in INPUTS.items():
        names = {
            "intro": "项目简介",
            "talk": "讲稿与问答",
            "tech": "技术契约",
            "runtime": "运行恢复",
            "todo": "唯一待办",
            "tests": "测试证据",
        }
        story.append(paragraph(f"{names[key]}：{html.escape(location)}", "small"))
    for location in DATA:
        story.append(paragraph(html.escape(location), "small"))
    story.extend(
        [
            paragraph(
                '源码仓库：<link href="https://github.com/XZQ/zhuguang" color="#087F8C">'
                "https://github.com/XZQ/zhuguang</link>",
                "small",
            ),
            heading("维护与导出"),
            paragraph(
                "1. 更新上述现行文档，完成受影响验证后同步事实源。<br/>"
                "2. 运行 uv run scripts/build_project_handbook.py。<br/>"
                "3. 核对数字、来源、链接、分页与图表，重建门户以复制这份新制品。<br/>"
                "4. 发布与真实环境验收独立执行；旧复赛 PDF 保持原路径、原字节。"
            ),
            note(
                "本手册替代三份复赛稿作为当前阅读入口。原复赛 PDF 是 2026-09-04 历史材料，"
                "其旧测试数、量化经营效果和平台已验证说法不作为当前事实。"
                "既有 PPT/PDF 与线上站点的发布版本另行核对。"
            ),
        ]
    )
    return story


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/msyh.ttc"))
    parser.add_argument("--bold-font", type=Path, default=Path("C:/Windows/Fonts/msyhbd.ttc"))
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    originals = list((ROOT / "docs/competition").glob("2026-GOAI复赛*.pdf"))
    original_paths = {file.resolve() for file in originals}
    source_paths = {(ROOT / location).resolve() for location in [*INPUTS.values(), *DATA]}
    if output in original_paths:
        raise ValueError("Historical PDF originals are not authoring targets")
    if output in source_paths:
        raise ValueError("PDF output cannot overwrite source documents")
    manifest = args.manifest.resolve() if args.manifest else None
    if manifest in original_paths | source_paths | {output}:
        raise ValueError("Manifest cannot overwrite PDF output, historical originals, or sources")
    preserved = {str(file): digest(file) for file in originals}
    edition = date.fromisoformat(args.date).isoformat()
    for font in [args.font, args.bold_font]:
        if not font.is_file():
            raise FileNotFoundError("Provide --font and --bold-font with Chinese TrueType fonts")
    pdfmetrics.registerFont(TTFont("ZG", str(args.font)))
    pdfmetrics.registerFont(TTFont("ZG-Bold", str(args.bold_font)))
    pdfmetrics.registerFontFamily(
        "ZG", normal="ZG", bold="ZG-Bold", italic="ZG", boldItalic="ZG-Bold"
    )
    global STYLES
    STYLES = {
        "body": style("body"),
        "small": style("small", 9, 14),
        "caption": style("caption", 9, 14, textTransform=None),
        "title": style("title", 24, 32, fontFamily="ZG", keepWithNext=True),
        "sub": style("sub", 12, 18, spaceBefore=10, keepWithNext=True),
        "cell": style("cell", 8.5, 12.5),
        "cell_head": style("cell_head", 8.5, 12.5),
        "code": style("code", 7.5, 10.6),
    }
    for name in ["title", "sub", "cell_head"]:
        STYLES[name].fontName = "ZG-Bold"
    STYLES["caption"].textColor = colors.HexColor(MUTED)
    STYLES["cell_head"].textColor = colors.white
    source_hashes = {location: digest(ROOT / location) for location in [*INPUTS.values(), *DATA]}
    sources = {
        key: MD((ROOT / location).read_text(encoding="utf-8")) for key, location in INPUTS.items()
    }
    facts = json.loads((ROOT / DATA[0]).read_text(encoding="utf-8"))
    ablation = json.loads((ROOT / DATA[1]).read_text(encoding="utf-8"))
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    story = make_story(sources, facts, ablation, edition, commit, source_hashes)
    output.parent.mkdir(parents=True, exist_ok=True)
    os.environ["SOURCE_DATE_EPOCH"] = str(
        int(datetime.fromisoformat(edition).replace(tzinfo=UTC).timestamp())
    )
    doc = Handbook(
        str(output),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=53,
        bottomMargin=51,
        title="店巡 Agent 项目与答辩手册",
        author="逐光队",
        subject="当前实现、演示、讲稿、问答与验证边界",
        pageCompression=1,
        invariant=1,
    )
    doc.edition, doc.sections = edition, []
    doc.addPageTemplates(
        [
            PageTemplate(
                id="handbook",
                frames=[
                    Frame(
                        MARGIN,
                        51,
                        CONTENT,
                        HEIGHT - 104,
                        leftPadding=0,
                        rightPadding=0,
                        topPadding=0,
                        bottomPadding=0,
                    )
                ],
                onPage=footer,
            )
        ]
    )
    doc.build(story)
    if preserved != {name: digest(Path(name)) for name in preserved}:
        raise RuntimeError("Historical PDF bytes changed")
    result = {
        "output": str(output),
        "date": edition,
        "pages": doc.page,
        "sha256": digest(output),
        "source_commit": commit,
        "source_hashes": source_hashes,
        "font_hashes": {str(font): digest(font) for font in [args.font, args.bold_font]},
        "sections": doc.sections,
        "historical_pdfs_unchanged": len(preserved),
    }
    if manifest:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
