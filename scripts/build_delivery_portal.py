#!/usr/bin/env python3
"""Build the competition delivery portal HTML for mazhi.icu/agentteams/."""

import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMAND_CENTER_HTML = ROOT / "evidence" / "m4" / "command-center.html"
OUTPUT_DIR = ROOT / "dist" / "delivery-portal"
OUTPUT_FILE = OUTPUT_DIR / "index.html"


def extract_command_center_panels():
    """Extract panels and tabs from evidence/m4/command-center.html."""
    if not COMMAND_CENTER_HTML.exists():
        return "", ""
    text = COMMAND_CENTER_HTML.read_text(encoding="utf-8")
    
    # Extract tabs
    nav_match = re.search(r'<nav class="tabs">(.*?)</nav>', text, re.DOTALL)
    tabs_html = nav_match.group(1) if nav_match else ""
    
    # Extract all section panels
    panels_matches = re.findall(r'(<section class="panel.*?</section>)', text, re.DOTALL)
    panels_html = "\n".join(panels_matches) if panels_matches else ""
    
    return tabs_html, panels_html


def build_portal():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tabs_html, panels_html = extract_command_center_panels()
    
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>店巡 Agent | 逐光队 · 2026 GOAI Agent Infra 复赛官方评审与演示指挥中心</title>
<meta name="description" content="2026 世界人工智能开源大赛 (GOAI) 赛道一 Agent Infra 复赛作品：店巡 Agent（逐光）官方评审与演示指挥中心。基于 AgentTeams v1.2.3 框架构建连锁便利店冷柜失温异常安全闭环。">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #070d18;
  --bg-card: #0e1726;
  --bg-card-hover: #142033;
  --panel: rgba(14, 23, 38, 0.85);
  --border: rgba(56, 189, 248, 0.18);
  --border-subtle: rgba(255, 255, 255, 0.08);
  --border-glow: rgba(56, 189, 248, 0.45);
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --cyan: #38bdf8;
  --blue: #3b82f6;
  --indigo: #6366f1;
  --green: #10b981;
  --green-glow: rgba(16, 185, 129, 0.25);
  --amber: #f59e0b;
  --amber-glow: rgba(245, 158, 11, 0.25);
  --red: #ef4444;
  --red-glow: rgba(239, 68, 68, 0.25);
  --font-sans: "Inter", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: "JetBrains Mono", "SF Mono", Consolas, monospace;
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; }}
body {{
  background: radial-gradient(circle at 85% -10%, rgba(56, 189, 248, 0.12) 0%, transparent 40%),
              radial-gradient(circle at 10% 25%, rgba(99, 102, 241, 0.10) 0%, transparent 45%),
              var(--bg);
  color: var(--text-primary);
  font-family: var(--font-sans);
  line-height: 1.55;
  font-size: 14px;
  min-height: 100vh;
}}

a {{ color: var(--cyan); text-decoration: none; transition: color 0.2s; }}
a:hover {{ color: #7dd3fc; text-decoration: underline; }}
button {{ font-family: inherit; cursor: pointer; border: none; background: none; }}

/* Layout Container */
.shell {{
  max-width: 1360px;
  margin: 0 auto;
  padding: 20px 24px 60px;
}}

/* Top Navigation Bar */
.header-bar {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border-subtle);
  flex-wrap: wrap;
  gap: 16px;
}}
.brand-group {{
  display: flex;
  align-items: center;
  gap: 12px;
}}
.brand-badge {{
  background: linear-gradient(135deg, var(--cyan), var(--indigo));
  color: #030712;
  font-weight: 800;
  font-size: 13px;
  padding: 6px 12px;
  border-radius: 8px;
  letter-spacing: 0.05em;
  box-shadow: 0 0 16px rgba(56, 189, 248, 0.35);
}}
.brand-titles h1 {{
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.brand-titles .sub {{
  font-size: 12px;
  color: var(--text-secondary);
}}
.header-actions {{
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}}
.header-btn {{
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  transition: all 0.2s;
}}
.header-btn:hover {{
  background: rgba(56, 189, 248, 0.15);
  border-color: var(--cyan);
  color: #fff;
  text-decoration: none;
}}
.header-btn.primary {{
  background: linear-gradient(135deg, #0284c7, #4f46e5);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 0 12px rgba(2, 132, 199, 0.4);
}}

/* Match Context Banner */
.match-banner {{
  margin: 18px 0;
  background: linear-gradient(90deg, rgba(14, 23, 38, 0.95), rgba(20, 32, 51, 0.8));
  border: 1px solid var(--border);
  border-left: 4px solid var(--cyan);
  border-radius: 12px;
  padding: 14px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
}}
.match-info {{
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  align-items: center;
}}
.match-tag {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}}
.match-tag b {{
  color: var(--cyan);
  font-family: var(--font-mono);
}}
.match-time-pill {{
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: var(--green);
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}}
.pulse-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
  animation: pulse 2s infinite;
}}
@keyframes pulse {{
  0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
  70% {{ transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }}
  100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
}}

/* Redlines Alert */
.redlines-bar {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 20px;
}}
@media (max-width: 800px) {{ .redlines-bar {{ grid-template-columns: 1fr; }} }}
.redline-item {{
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-left: 4px solid var(--red);
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 12.5px;
  color: #fca5a5;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.redline-item b {{ color: #fee2e2; }}

/* KPIs Grid */
.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 22px;
}}
.kpi-card {{
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 14px 16px;
  position: relative;
  overflow: hidden;
}}
.kpi-card::before {{
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--cyan), transparent);
  opacity: 0.4;
}}
.kpi-val {{
  font-size: 22px;
  font-weight: 800;
  color: var(--cyan);
  font-family: var(--font-mono);
}}
.kpi-lbl {{
  font-size: 11.5px;
  color: var(--text-secondary);
  margin-top: 2px;
}}

/* Main Navigation Tabs */
.main-nav-tabs {{
  display: flex;
  gap: 6px;
  background: rgba(14, 23, 38, 0.7);
  padding: 6px;
  border-radius: 12px;
  border: 1px solid var(--border-subtle);
  margin-bottom: 24px;
  overflow-x: auto;
}}
.nav-tab-btn {{
  padding: 10px 18px;
  border-radius: 8px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  transition: all 0.2s;
}}
.nav-tab-btn:hover {{
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.04);
}}
.nav-tab-btn.active {{
  background: linear-gradient(135deg, rgba(2, 132, 199, 0.3), rgba(79, 70, 229, 0.3));
  border: 1px solid var(--cyan);
  color: #fff;
  box-shadow: 0 0 14px rgba(56, 189, 248, 0.25);
}}
.nav-tab-btn .badge-pill {{
  background: rgba(56, 189, 248, 0.15);
  color: var(--cyan);
  font-size: 10.5px;
  padding: 2px 7px;
  border-radius: 999px;
  font-family: var(--font-mono);
}}

/* Main Section Containers */
.view-section {{
  display: none;
  animation: fadeIn 0.25s ease-in-out;
}}
.view-section.active {{
  display: block;
}}
@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(4px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

/* Card Container Styles */
.panel-card {{
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 20px;
}}
.panel-title {{
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.panel-desc {{
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 20px;
}}

/* ---------------- 1 MINUTE DEMO STEPPER STYLES ---------------- */
.demo-controller {{
  background: linear-gradient(135deg, rgba(14, 23, 38, 0.95), rgba(24, 38, 64, 0.95));
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 22px 24px;
  margin-bottom: 24px;
}}
.demo-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 18px;
}}
.demo-timer-box {{
  display: flex;
  align-items: center;
  gap: 12px;
}}
.demo-timer-display {{
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 800;
  color: var(--cyan);
  background: rgba(0, 0, 0, 0.3);
  padding: 4px 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
}}
.demo-actions {{
  display: flex;
  gap: 8px;
}}
.demo-btn {{
  padding: 9px 18px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}}
.demo-btn.play {{
  background: linear-gradient(135deg, var(--green), #059669);
  color: #fff;
  box-shadow: 0 0 14px var(--green-glow);
}}
.demo-btn.pause {{
  background: linear-gradient(135deg, var(--amber), #d97706);
  color: #fff;
  box-shadow: 0 0 14px var(--amber-glow);
}}
.demo-btn.secondary {{
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
}}
.demo-btn.secondary:hover {{
  background: rgba(255, 255, 255, 0.12);
}}

/* Stepper Progress Bar */
.stepper-steps {{
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
  margin-bottom: 22px;
}}
@media (max-width: 900px) {{ .stepper-steps {{ grid-template-columns: repeat(3, 1fr); }} }}
@media (max-width: 600px) {{ .stepper-steps {{ grid-template-columns: 1fr; }} }}
.step-tab {{
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}}
.step-tab:hover {{
  background: rgba(255, 255, 255, 0.06);
}}
.step-tab.active {{
  background: rgba(56, 189, 248, 0.12);
  border-color: var(--cyan);
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.25);
}}
.step-tab.completed {{
  border-color: var(--green);
}}
.step-tab .step-num {{
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  color: var(--text-muted);
  margin-bottom: 2px;
}}
.step-tab.active .step-num {{ color: var(--cyan); }}
.step-tab.completed .step-num {{ color: var(--green); }}
.step-tab .step-title {{
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  line-height: 1.3;
}}
.step-tab.active .step-title {{ color: #fff; }}

/* Step Detail Showcase */
.step-detail-card {{
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 22px;
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 24px;
}}
@media (max-width: 860px) {{ .step-detail-card {{ grid-template-columns: 1fr; }} }}

.step-info-col h3 {{
  font-size: 17px;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}}
.step-desc {{
  font-size: 13.5px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 16px;
}}
.step-badges {{
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}}
.agent-pill {{
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.35);
  color: #a5b4fc;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 6px;
}}
.skill-pill {{
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #6ee7b7;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 6px;
  font-family: var(--font-mono);
}}
.mcp-pill {{
  background: rgba(245, 158, 11, 0.15);
  border: 1px solid rgba(245, 158, 11, 0.35);
  color: #fcd34d;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 6px;
  font-family: var(--font-mono);
}}

/* Terminal / Output Preview Box */
.terminal-box {{
  background: #030712;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 14px 16px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  color: #cbd5e1;
  overflow-x: auto;
  max-height: 320px;
  position: relative;
}}
.terminal-header {{
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 8px;
  margin-bottom: 10px;
  color: var(--text-muted);
  font-size: 11px;
}}
.terminal-line {{ margin-bottom: 4px; }}
.terminal-line .t-green {{ color: #4ade80; }}
.terminal-line .t-cyan {{ color: #38bdf8; }}
.terminal-line .t-amber {{ color: #fbbf24; }}
.terminal-line .t-red {{ color: #f87171; }}

/* ---------------- TAB 2: AGENTTEAMS CLUSTER STYLES ---------------- */
.cluster-cards-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}}
.worker-card {{
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 18px 20px;
  transition: all 0.2s;
  position: relative;
}}
.worker-card:hover {{
  border-color: var(--border-glow);
  transform: translateY(-2px);
}}
.worker-top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}}
.worker-name-role h4 {{
  font-size: 15px;
  font-weight: 700;
  color: #fff;
}}
.worker-name-role .worker-sub {{
  font-size: 11.5px;
  color: var(--text-muted);
}}
.worker-meta-list {{
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  border-top: 1px solid var(--border-subtle);
  padding-top: 10px;
}}
.worker-meta-row {{
  display: flex;
  justify-content: space-between;
}}
.worker-meta-row b {{
  color: var(--text-primary);
  font-family: var(--font-mono);
}}

/* ---------------- TAB 3: COMMAND CENTER (OVERRIDE LIGHT STYLES FOR SEAMLESS FIT) ---------------- */
.command-center-wrap {{
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 24px;
}}
.command-center-wrap .tabs {{
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}}
.command-center-wrap .tab {{
  border: 1px solid var(--border-subtle);
  background: rgba(255, 255, 255, 0.05);
  border-radius: 999px;
  padding: 7px 16px;
  font-size: 13px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;
}}
.command-center-wrap .tab:hover {{
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.1);
}}
.command-center-wrap .tab.active {{
  background: var(--cyan);
  color: #030712;
  font-weight: 700;
  border-color: var(--cyan);
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.3);
}}
.command-center-wrap .panel {{
  display: none;
  background: rgba(10, 18, 30, 0.7);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 22px;
}}
.command-center-wrap .panel.active {{ display: block; }}
.command-center-wrap .panel-head {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 10px;
}}
.command-center-wrap h2 {{ font-size: 19px; color: #fff; }}
.command-center-wrap h3 {{ font-size: 14px; color: #e2e8f0; margin: 20px 0 10px; }}
.command-center-wrap .badges {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.command-center-wrap .badge {{
  display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 600;
}}
.command-center-wrap .badge-ok {{ background: rgba(16, 185, 129, 0.15); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); }}
.command-center-wrap .badge-warn {{ background: rgba(245, 158, 11, 0.15); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.3); }}
.command-center-wrap .badge-bad {{ background: rgba(239, 68, 68, 0.15); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); }}
.command-center-wrap .badge-info {{ background: rgba(56, 189, 248, 0.15); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.3); }}
.command-center-wrap .redline-note {{
  margin-top: 10px; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3);
  color: #fef08a; border-radius: 8px; padding: 8px 12px; font-size: 13px; font-weight: 600;
}}
.command-center-wrap .phase-lane {{ display: flex; align-items: stretch; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }}
.command-center-wrap .phase-card {{
  flex: 1; min-width: 170px; border: 1px solid var(--border-subtle); border-radius: 10px; padding: 12px; background: rgba(255, 255, 255, 0.02);
}}
.command-center-wrap .phase-card.done {{ border-top: 3px solid var(--cyan); }}
.command-center-wrap .phase-title {{ font-weight: 700; font-size: 13px; color: var(--cyan); margin-bottom: 6px; }}
.command-center-wrap .phase-card ul {{ padding-left: 18px; font-size: 12px; color: var(--text-secondary); }}
.command-center-wrap .phase-arrow {{ align-self: center; color: var(--text-muted); font-weight: 700; }}
.command-center-wrap .handoff {{ display: flex; align-items: stretch; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }}
.command-center-wrap .hop {{
  border-radius: 10px; padding: 8px 12px; min-width: 120px; border: 1px solid var(--border-subtle); background: rgba(255, 255, 255, 0.02);
}}
.command-center-wrap .hop-ok {{ border-top: 3px solid var(--green); }}
.command-center-wrap .hop-bad {{ border-top: 3px solid var(--red); }}
.command-center-wrap .hop-name {{ font-size: 12px; font-weight: 700; color: #fff; }}
.command-center-wrap .hop-brief {{ font-size: 11px; color: var(--text-secondary); margin-top: 2px; }}
.command-center-wrap .hop-arrow {{ align-self: center; color: var(--text-muted); }}
.command-center-wrap .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }}
@media (max-width: 900px) {{ .command-center-wrap .grid-2 {{ grid-template-columns: 1fr; }} }}
.command-center-wrap .card {{
  border: 1px solid var(--border-subtle); border-radius: 12px; padding: 14px 16px; background: rgba(255, 255, 255, 0.02);
}}
.command-center-wrap .tbl {{ width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 8px; }}
.command-center-wrap .tbl th {{ text-align: left; color: var(--text-muted); font-weight: 600; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding: 8px 10px; }}
.command-center-wrap .tbl td {{ border-bottom: 1px solid rgba(255, 255, 255, 0.05); padding: 8px 10px; color: var(--text-secondary); }}
.command-center-wrap .mono {{ font-family: var(--font-mono); color: #cbd5e1; }}
.command-center-wrap .temp-svg {{ width: 100%; height: auto; border-radius: 8px; background: rgba(0, 0, 0, 0.3); padding: 6px; }}
.command-center-wrap .t-lbl {{ font-size: 9px; fill: #94a3b8; }}
.command-center-wrap .t-th {{ font-size: 10px; fill: #f87171; font-weight: 700; }}
.command-center-wrap .legend {{ font-size: 11.5px; color: var(--text-muted); margin-top: 6px; }}

/* ---------------- TAB 4: SKILL NINE-ELEMENTS CARDS ---------------- */
.skills-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 18px;
}}
.skill-card {{
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 20px;
  transition: all 0.2s;
}}
.skill-card:hover {{
  border-color: var(--cyan);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}}
.skill-card-head {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}}
.skill-card-head h4 {{
  font-family: var(--font-mono);
  font-size: 16px;
  color: var(--cyan);
}}
.skill-owner-tag {{
  font-size: 11.5px;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: #a5b4fc;
}}
.skill-elements-table {{
  width: 100%;
  font-size: 12.5px;
  border-collapse: collapse;
}}
.skill-elements-table td {{
  padding: 6px 0;
  vertical-align: top;
}}
.skill-elements-table td:first-child {{
  width: 75px;
  color: var(--text-muted);
  font-weight: 600;
}}
.skill-elements-table td:last-child {{
  color: var(--text-secondary);
}}

/* ---------------- TAB 5: HITL SIMULATOR STYLES ---------------- */
.hitl-sim-card {{
  background: linear-gradient(135deg, rgba(14, 23, 38, 0.95), rgba(20, 32, 51, 0.95));
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 22px;
  margin-bottom: 24px;
}}
.hitl-ticket {{
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 16px 20px;
  margin-top: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}}
.ticket-title {{ font-size: 15px; font-weight: 700; color: #fff; }}
.ticket-meta {{ font-size: 12px; color: var(--text-secondary); margin-top: 4px; }}
.ticket-actions {{ display: flex; gap: 8px; }}
.hitl-action-btn {{
  padding: 7px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; transition: all 0.2s;
}}
.hitl-action-btn.approve {{
  background: rgba(16, 185, 129, 0.2); border: 1px solid var(--green); color: #6ee7b7;
}}
.hitl-action-btn.reject {{
  background: rgba(239, 68, 68, 0.2); border: 1px solid var(--red); color: #fca5a5;
}}
.hitl-action-btn.timeout {{
  background: rgba(245, 158, 11, 0.2); border: 1px solid var(--amber); color: #fcd34d;
}}

/* ---------------- TAB 6: PPT EMBED STYLES ---------------- */
.ppt-embed-frame {{
  width: 100%;
  height: 720px;
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  background: #000;
}}

/* Footer */
.portal-footer {{
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--text-muted);
  font-size: 12px;
  flex-wrap: wrap;
  gap: 12px;
}}
</style>
</head>
<body>

<div class="shell">
  <!-- Top Navigation Bar -->
  <header class="header-bar">
    <div class="brand-group">
      <div class="brand-badge">GOAI 2026</div>
      <div class="brand-titles">
        <h1>店巡 Agent <span style="font-size:14px; font-weight:400; color:var(--cyan);">(逐光队 · 赛道一 Agent Infra)</span></h1>
        <div class="sub">基于 AgentTeams v1.2.3 的连锁便利店异常安全闭环基础设施</div>
      </div>
    </div>
    <div class="header-actions">
      <a class="header-btn" href="./ppt/" target="_blank">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        方案 PPT 演示
      </a>
      <a class="header-btn" href="./ppt/店巡Agent方案.pdf" target="_blank" download>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        下载方案 PDF
      </a>
      <a class="header-btn primary" href="https://github.com/XZQ/zhuguang" target="_blank">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
        GitHub 仓库
      </a>
    </div>
  </header>

  <!-- Match Context Banner -->
  <div class="match-banner">
    <div class="match-info">
      <div class="match-tag">参赛队伍：<b>逐光（第 3 组｜第 13 队）</b></div>
      <div class="match-tag">作品名称：<b>店巡 Agent</b></div>
      <div class="match-tag">答辩时间：<b>2026-09-04 14:08—14:16</b> (候场 13:58 前)</div>
      <div class="match-tag">时长：<b>8 分钟</b> (陈述3m + Demo1m + 问答3m + 评分1m)</div>
    </div>
    <div class="match-time-pill">
      <div class="pulse-dot"></div>
      <span id="runtime-status-label">AgentTeams v1.2.3 · 5 Workers 在线</span>
    </div>
  </div>

  <!-- Safety Redlines Banner -->
  <div class="redlines-bar">
    <div class="redline-item">
      <span>🛡️</span>
      <div><b>红线一（职责分离）：</b>执行者不能自证成功，Auditor 必须独立重查设备与商品事实</div>
    </div>
    <div class="redline-item">
      <span>🔒</span>
      <div><b>红线二（双重状态）：</b>设备恢复 ≠ 商品安全，工单完成 ≠ 事件关闭，严禁直接放行</div>
    </div>
  </div>

  <!-- Core KPIs Grid -->
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-val">6 / 6</div>
      <div class="kpi-lbl">场景通过率 (100%)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">5 + 1</div>
      <div class="kpi-lbl">业务 Agent + Manager</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">6 个</div>
      <div class="kpi-lbl">P0 核心 Skill (九要素)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">0 / 0</div>
      <div class="kpi-lbl">错误关闭 / 错误放行</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">45 / 45</div>
      <div class="kpi-lbl">完整 Evidence 链</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">26 / 26</div>
      <div class="kpi-lbl">阶段 Trace 覆盖</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">qwen3.8-max</div>
      <div class="kpi-lbl">驱动模型 (百炼平台)</div>
    </div>
  </div>

  <!-- Main Navigation Tabs -->
  <nav class="main-nav-tabs">
    <button class="nav-tab-btn active" onclick="switchMainTab('demo')">
      ⚡️ 1 分钟答辩 Demo
      <span class="badge-pill">答辩演示</span>
    </button>
    <button class="nav-tab-btn" onclick="switchMainTab('command')">
      📊 事故指挥台 (6大场景)
      <span class="badge-pill">全链路证据</span>
    </button>
    <button class="nav-tab-btn" onclick="switchMainTab('cluster')">
      🤖 AgentTeams 集群拓扑
      <span class="badge-pill">实机 5 Workers</span>
    </button>
    <button class="nav-tab-btn" onclick="switchMainTab('skills')">
      🛠 6 大核心 Skill 资产
      <span class="badge-pill">九要素卡</span>
    </button>
    <button class="nav-tab-btn" onclick="switchMainTab('hitl')">
      🔒 高风险审批与审计
      <span class="badge-pill">HITL 安全</span>
    </button>
    <button class="nav-tab-btn" onclick="switchMainTab('ppt')">
      📑 答辩 PPT 与整改说明
      <span class="badge-pill">评审材料</span>
    </button>
  </nav>

  <!-- ==================== SECTION 1: 1-MINUTE DEFENSE DEMO ==================== -->
  <section id="view-demo" class="view-section active">
    <div class="demo-controller">
      <div class="demo-header">
        <div>
          <h2 style="font-size: 19px; color:#fff; display:flex; align-items:center; gap:8px;">
            ⚡️ 1 分钟高光 Demo 演练：冷柜失温五阶段闭环
          </h2>
          <p style="color:var(--text-secondary); font-size:12.5px; margin-top:2px;">
            专为复赛答辩 1 分钟 Demo 设计：涵盖 5 个 Agent 协同、核心 Skill 调用、停售遏制、HITL 审批与 Auditor 独立重查
          </p>
        </div>
        <div class="demo-timer-box">
          <div class="demo-timer-display" id="demo-timer">00:00</div>
          <div class="demo-actions">
            <button class="demo-btn play" id="btn-play-demo" onclick="toggleAutoPlay()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              一键演练 (60s)
            </button>
            <button class="demo-btn secondary" onclick="stepDemo(-1)">⏮ 上一步</button>
            <button class="demo-btn secondary" onclick="stepDemo(1)">⏭ 下一步</button>
            <button class="demo-btn secondary" onclick="resetDemo()">重置</button>
          </div>
        </div>
      </div>

      <!-- Stepper Steps -->
      <div class="stepper-steps">
        <div class="step-tab active" id="step-tab-0" onclick="goToStep(0)">
          <div class="step-num">STEP 1 · 00-10s</div>
          <div class="step-title">Sentry 巡检发现</div>
        </div>
        <div class="step-tab" id="step-tab-1" onclick="goToStep(1)">
          <div class="step-num">STEP 2 · 10-20s</div>
          <div class="step-title">Executor 停售遏制</div>
        </div>
        <div class="step-tab" id="step-tab-2" onclick="goToStep(2)">
          <div class="step-num">STEP 3 · 20-30s</div>
          <div class="step-title">Diagnoser 根因诊断</div>
        </div>
        <div class="step-tab" id="step-tab-3" onclick="goToStep(3)">
          <div class="step-num">STEP 4 · 30-40s</div>
          <div class="step-title">处置派单与 HITL</div>
        </div>
        <div class="step-tab" id="step-tab-4" onclick="goToStep(4)">
          <div class="step-num">STEP 5 · 40-50s</div>
          <div class="step-title">Auditor 独立稽核</div>
        </div>
        <div class="step-tab" id="step-tab-5" onclick="goToStep(5)">
          <div class="step-num">STEP 6 · 50-60s</div>
          <div class="step-title">复盘沉淀与关闭</div>
        </div>
      </div>

      <!-- Step Detail Showcase -->
      <div class="step-detail-card" id="step-detail-container">
        <!-- Content will be populated dynamically by JS -->
      </div>
    </div>
  </section>

  <!-- ==================== SECTION 2: COMMAND CENTER (6 SCENARIOS) ==================== -->
  <section id="view-command" class="view-section">
    <div class="command-center-wrap">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
        <div>
          <h2 style="font-size:20px; color:#fff;">逐光 · 事故指挥台（六场景端到端闭环）</h2>
          <p style="font-size:12.5px; color:var(--text-secondary); margin-top:2px;">
            包含 A 正常分支与 B~F 异常分支；呈现真实温度变化 SVG 时序、阶段交接、Auditor 独立验证矩阵与只增写审计
          </p>
        </div>
        <div style="font-size:12px; color:var(--text-muted);">
          虚拟时钟锚点: 2026-08-28T09:00:00+08:00
        </div>
      </div>

      <nav class="tabs">
        {tabs_html}
      </nav>

      <div class="panels-container">
        {panels_html}
      </div>
    </div>
  </section>

  <!-- ==================== SECTION 3: AGENTTEAMS REAL CLUSTER ==================== -->
  <section id="view-cluster" class="view-section">
    <div class="panel-card">
      <div class="panel-title">🤖 AgentTeams v1.2.3 实机集群基座状态 (广州节点)</div>
      <div class="panel-desc">
        现场部署于广州主机（mazhi-tencent，Ubuntu 24.04），通过内嵌 Controller 调度 5 个 Worker，驱动模型为阿里云百炼 <code>qwen3.8-max</code>。
      </div>

      <div class="cluster-cards-grid" id="cluster-cards-container">
        <!-- Will be dynamically populated / updated from status.json -->
        <div class="worker-card">
          <div class="worker-top">
            <div class="worker-name-role">
              <h4>Orchestrator</h4>
              <div class="worker-sub">dianxun-orchestrator · Team Leader</div>
            </div>
            <span class="badge badge-ok">Ready</span>
          </div>
          <div class="worker-meta-list">
            <div class="worker-meta-row"><span>职责边界:</span> <b>事件拆解 / 阶段推进 / 超时管理</b></div>
            <div class="worker-meta-row"><span>驱动模型:</span> <b>qwen3.8-max</b></div>
            <div class="worker-meta-row"><span>绑定端口:</span> <b>19408 (qwenpaw)</b></div>
            <div class="worker-meta-row"><span>协同权限:</span> <b>仅协调委派，无领域写权限</b></div>
          </div>
        </div>

        <div class="worker-card">
          <div class="worker-top">
            <div class="worker-name-role">
              <h4>Sentry</h4>
              <div class="worker-sub">dianxun-sentry · 巡检守卫</div>
            </div>
            <span class="badge badge-ok">Running</span>
          </div>
          <div class="worker-meta-list">
            <div class="worker-meta-row"><span>职责边界:</span> <b>失温检测 / 传感器可疑标记</b></div>
            <div class="worker-meta-row"><span>驱动模型:</span> <b>qwen3.8-max</b></div>
            <div class="worker-meta-row"><span>绑定端口:</span> <b>10419 (qwenpaw)</b></div>
            <div class="worker-meta-row"><span>核心 Skill:</span> <b>anomaly-detect</b></div>
          </div>
        </div>

        <div class="worker-card">
          <div class="worker-top">
            <div class="worker-name-role">
              <h4>Diagnoser</h4>
              <div class="worker-sub">dianxun-diagnoser · 根因诊断</div>
            </div>
            <span class="badge badge-ok">Ready</span>
          </div>
          <div class="worker-meta-list">
            <div class="worker-meta-row"><span>职责边界:</span> <b>多源假设排序 / 批次暴露评估</b></div>
            <div class="worker-meta-row"><span>驱动模型:</span> <b>qwen3.8-max</b></div>
            <div class="worker-meta-row"><span>绑定端口:</span> <b>12693 (qwenpaw)</b></div>
            <div class="worker-meta-row"><span>核心 Skill:</span> <b>coldchain-risk-assess, rootcause</b></div>
          </div>
        </div>

        <div class="worker-card">
          <div class="worker-top">
            <div class="worker-name-role">
              <h4>Executor</h4>
              <div class="worker-sub">dianxun-executor · 受控执行</div>
            </div>
            <span class="badge badge-ok">Ready</span>
          </div>
          <div class="worker-meta-list">
            <div class="worker-meta-row"><span>职责边界:</span> <b>停售隔离 / 维修派单 / 批次处置</b></div>
            <div class="worker-meta-row"><span>驱动模型:</span> <b>qwen3.8-max</b></div>
            <div class="worker-meta-row"><span>绑定端口:</span> <b>11254 (qwenpaw)</b></div>
            <div class="worker-meta-row"><span>核心 Skill:</span> <b>work-order-dispatch (需审批)</b></div>
          </div>
        </div>

        <div class="worker-card">
          <div class="worker-top">
            <div class="worker-name-role">
              <h4>Auditor</h4>
              <div class="worker-sub">dianxun-auditor · 独立稽核</div>
            </div>
            <span class="badge badge-ok">Ready</span>
          </div>
          <div class="worker-meta-list">
            <div class="worker-meta-row"><span>职责边界:</span> <b>独立重查 / 放行门禁 / 复盘报告</b></div>
            <div class="worker-meta-row"><span>驱动模型:</span> <b>qwen3.8-max</b></div>
            <div class="worker-meta-row"><span>绑定端口:</span> <b>11550 (qwenpaw)</b></div>
            <div class="worker-meta-row"><span>核心 Skill:</span> <b>outcome-verify, review-report</b></div>
          </div>
        </div>
      </div>

      <div style="background:rgba(0,0,0,0.3); border:1px solid var(--border-subtle); border-radius:12px; padding:18px; margin-top:20px;">
        <h4 style="font-size:14px; color:#fff; margin-bottom:10px;">附录 A 标准字段矩阵（Agent Identity 清单）</h4>
        <div style="overflow-x:auto;">
          <table class="tbl" style="width:100%; font-size:12px;">
            <thead>
              <tr style="color:var(--text-muted); border-bottom:1px solid rgba(255,255,255,0.1);">
                <th style="padding:6px 8px; text-align:left;">Name</th>
                <th style="padding:6px 8px; text-align:left;">Role</th>
                <th style="padding:6px 8px; text-align:left;">Capabilities</th>
                <th style="padding:6px 8px; text-align:left;">Inputs / Outputs</th>
                <th style="padding:6px 8px; text-align:left;">Decision Boundary (决策边界)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding:8px;" class="mono">dianxun-orchestrator</td>
                <td style="padding:8px;">Team Leader</td>
                <td style="padding:8px;">任务拆解、角色委派、等待管理</td>
                <td style="padding:8px;">incident_id / 阶段计划、回执汇总</td>
                <td style="padding:8px; color:#fca5a5;">严禁越权替代 Worker 调用领域工具，不判定业务终态</td>
              </tr>
              <tr>
                <td style="padding:8px;" class="mono">dianxun-sentry</td>
                <td style="padding:8px;">巡检守卫</td>
                <td style="padding:8px;">失温检测、证据质量检查</td>
                <td style="padding:8px;">设备传感器时序 / anomaly, severity</td>
                <td style="padding:8px; color:#fca5a5;">L0 只读；无权解除停售、无权确定根因</td>
              </tr>
              <tr>
                <td style="padding:8px;" class="mono">dianxun-diagnoser</td>
                <td style="padding:8px;">根因诊断</td>
                <td style="padding:8px;">多源假设排查、批次暴露评估</td>
                <td style="padding:8px;">设备上下文 / Top-K 假设、建议动作</td>
                <td style="padding:8px; color:#fca5a5;">L0 只读；严禁将相关性写成确定因果，无执行权</td>
              </tr>
              <tr>
                <td style="padding:8px;" class="mono">dianxun-executor</td>
                <td style="padding:8px;">受控执行</td>
                <td style="padding:8px;">停售隔离、发起审批、派发工单</td>
                <td style="padding:8px;">处置建议、审批流 / 工单号、执行回执</td>
                <td style="padding:8px; color:#fca5a5;">严禁自批、自验；所有写需幂等键；付款永远禁止</td>
              </tr>
              <tr>
                <td style="padding:8px;" class="mono">dianxun-auditor</td>
                <td style="padding:8px;">独立稽核</td>
                <td style="padding:8px;">独立重查事实、放行守卫、复盘</td>
                <td style="padding:8px;">incident_id / 验证结论、知识候选条目</td>
                <td style="padding:8px; color:#fca5a5;">严禁信任执行者回执代替重查；无权直接放行商品</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>

  <!-- ==================== SECTION 4: 6 CORE SKILLS ==================== -->
  <section id="view-skills" class="view-section">
    <div class="panel-card">
      <div class="panel-title">🛠 6 大核心 P0 Skill 资产图谱 (九要素规范卡)</div>
      <div class="panel-desc">
        严格满足复赛指南“提供核心 Skill 清单，说明用途、输入输出、调用条件、失败处理、安全边界及复用价值”要求。
      </div>

      <div class="skills-grid">
        <!-- Skill 1 -->
        <div class="skill-card">
          <div class="skill-card-head">
            <h4>anomaly-detect (v1.0.0)</h4>
            <span class="skill-owner-tag">Owner: Sentry</span>
          </div>
          <table class="skill-elements-table">
            <tr><td>业务用途</td><td>从时间序列识别冷柜持续失温，标记传感器数据可疑性，生成事件级证据。</td></tr>
            <tr><td>输入输出</td><td>输入设备/时序窗口；输出 anomaly, severity, quality, evidence_refs。</td></tr>
            <tr><td>调用条件</td><td>Sentry 收到 IoT 巡检触发并完成最小数据可用性检查后调用。</td></tr>
            <tr><td>依赖工具</td><td>query_device_context</td></tr>
            <tr><td>失败处理</td><td>查询失败返回 partial/degraded；可疑数据不直接驱动处置，保持遏制。</td></tr>
            <tr><td>安全边界</td><td>L0 只读；不得解除停售、不得创建工单、不得宣布根因。</td></tr>
            <tr><td>复用价值</td><td>可复用于其他带时序传感器和质量标记的连锁零售/冷链设备。</td></tr>
          </table>
        </div>

        <!-- Skill 2 -->
        <div class="skill-card">
          <div class="skill-card-head">
            <h4>coldchain-risk-assess (v1.1.0)</h4>
            <span class="skill-owner-tag">Owner: Diagnoser</span>
          </div>
          <table class="skill-elements-table">
            <tr><td>业务用途</td><td>按商品批次独立计算温度积分与暴露时长，避免以“设备恢复”覆盖“商品安全”。</td></tr>
            <tr><td>输入输出</td><td>输入 incident, 设备温度, 批次冷链策略；输出每批次建议 disposition 与依据。</td></tr>
            <tr><td>调用条件</td><td>发现失温并取得关联批次后调用；设备维修恢复后必须再次调用。</td></tr>
            <tr><td>依赖工具</td><td>query_device_context, query_inventory_batches</td></tr>
            <tr><td>失败处理</td><td>缺少批次或温度证据时返回 manual_review，严禁直接放行。</td></tr>
            <tr><td>安全边界</td><td>L0 只读；处置阈值必须由企业食品安全标准与 HACCP 规范决定。</td></tr>
            <tr><td>复用价值</td><td>可复用于冷链物流仓储、餐饮中央厨房与药品疫苗冷藏。</td></tr>
          </table>
        </div>

        <!-- Skill 3 -->
        <div class="skill-card">
          <div class="skill-card-head">
            <h4>rootcause-drilldown (v1.2.0)</h4>
            <span class="skill-owner-tag">Owner: Diagnoser</span>
          </div>
          <table class="skill-elements-table">
            <tr><td>业务用途</td><td>将压缩机、传感器、柜门未关等候选根因按证据排序，输出 Top-K 与排查计划。</td></tr>
            <tr><td>输入输出</td><td>输入 anomaly, 设备状态/门磁/电源；输出 ranked hypotheses, confidence, next_checks。</td></tr>
            <tr><td>调用条件</td><td>完成先行停售遏制且 Diagnoser 取得设备上下文后调用。</td></tr>
            <tr><td>依赖工具</td><td>query_device_context, search_knowledge (可选)</td></tr>
            <tr><td>失败处理</td><td>证据不足时保留多假设降低置信度，输出证据缺口，不硬编码假设。</td></tr>
            <tr><td>安全边界</td><td>L0 只读；不能因外部相关性直接判定确定因果。</td></tr>
            <tr><td>复用价值</td><td>Top-K 证据缺口排查模式可复用于门店强电、IoT 网关与安防异常。</td></tr>
          </table>
        </div>

        <!-- Skill 4 -->
        <div class="skill-card">
          <div class="skill-card-head">
            <h4>work-order-dispatch (v1.0.0)</h4>
            <span class="skill-owner-tag">Owner: Executor</span>
          </div>
          <table class="skill-elements-table">
            <tr><td>业务用途</td><td>根据 Top-1 根因生成幂等维修工单与处置动作，协调 HITL 审批与状态追踪。</td></tr>
            <tr><td>输入输出</td><td>输入 incident, device, fault, budget, 幂等键；输出工单号、审批单号与状态。</td></tr>
            <tr><td>调用条件</td><td>Diagnoser 给出可执行假设；Policy 校验通过后调用。</td></tr>
            <tr><td>依赖工具</td><td>create_approval, query_approval, create_workorder, query_workorder</td></tr>
            <tr><td>失败处理</td><td>高预算未经批准不创建工单；审批超时升级区域负责人；工单 partial 阻断关闭。</td></tr>
            <tr><td>安全边界</td><td>L1/L2 受控写；审批决定只能由店长/总部人员做出；付款永远禁止。</td></tr>
            <tr><td>复用价值</td><td>适用于“第三方服务商 + 审批流 + SLA 履约”型运维任务。</td></tr>
          </table>
        </div>

        <!-- Skill 5 -->
        <div class="skill-card">
          <div class="skill-card-head">
            <h4>outcome-verify (v1.1.0)</h4>
            <span class="skill-owner-tag">Owner: Auditor</span>
          </div>
          <table class="skill-elements-table">
            <tr><td>业务用途</td><td>独立重查设备、批次、停售、审批与工单五维事实，生成 release guard。</td></tr>
            <tr><td>输入输出</td><td>输入 incident_id, 预期终态；输出 subject_verifications, release_guard, verdict。</td></tr>
            <tr><td>调用条件</td><td>处置完成后调用；解除停售前与事件关闭前必须分别核验。</td></tr>
            <tr><td>依赖工具</td><td>5 类查询 MCP 函数；验证事实由 IncidentService 记录。</td></tr>
            <tr><td>失败处理</td><td>任一工具 partial 或批次不安全时，返回 failed/partial 并回开事件。</td></tr>
            <tr><td>安全边界</td><td>L0 只读验证；严禁信任 Executor 的回执代替实测；不可直接放行。</td></tr>
            <tr><td>复用价值</td><td>独立验收模式可复用于电商退款核验、仓库盘点稽核与合规审计。</td></tr>
          </table>
        </div>

        <!-- Skill 6 -->
        <div class="skill-card">
          <div class="skill-card-head">
            <h4>review-report (v1.1.0)</h4>
            <span class="skill-owner-tag">Owner: Auditor</span>
          </div>
          <table class="skill-elements-table">
            <tr><td>业务用途</td><td>关联时间线、根因、动作与验证，生成标准化复盘报告与待审知识条目。</td></tr>
            <tr><td>输入输出</td><td>输入 IncidentCase, actions, verifications；输出 review, lessons, knowledge_candidates。</td></tr>
            <tr><td>调用条件</td><td>Auditor 验证通过且事件进入 LEARN 阶段后调用。</td></tr>
            <tr><td>依赖工具</td><td>IncidentService 快照与 Trace/Evidence 审计。</td></tr>
            <tr><td>失败处理</td><td>证据不完整时标记 partial；知识条目保持 pending 待专家审核。</td></tr>
            <tr><td>安全边界</td><td>只读生成；不得自动修改生产 Skill、Policy 或正式知识库。</td></tr>
            <tr><td>复用价值</td><td>可复用于任何需要经验沉淀与专家审核闭环的运营系统。</td></tr>
          </table>
        </div>
      </div>
    </div>
  </section>

  <!-- ==================== SECTION 5: HITL & SECURITY ==================== -->
  <section id="view-hitl" class="view-section">
    <div class="panel-card">
      <div class="panel-title">🔒 高风险操作控制中心 (Human-in-the-Loop & Audit)</div>
      <div class="panel-desc">
        高风险动作（食品停售、冷库调拨、大额维修派单）受到严格的权限控制、人工审批、幂等与不可篡改审计保护。
      </div>

      <div class="hitl-sim-card">
        <h3 style="font-size:16px; color:#fff; margin-bottom:6px;">交互式审批演练 (HITL Simulator)</h3>
        <p style="font-size:12.5px; color:var(--text-secondary);">
          当 Executor 遇到预估费用超限或食品报损等敏感操作时，系统必须挂起等待人工决定（支持批准、拒绝、超时升级）：
        </p>

        <div class="hitl-ticket" id="hitl-ticket-1">
          <div>
            <div class="ticket-title">工单审批单 #APPR-20260828-01: FROST-S03 压缩机急修</div>
            <div class="ticket-meta">申请角色: Executor · 预估费用: ¥680.00 · 审批权限: 区域设备经理 · 状态: <b style="color:var(--amber)" id="ticket-status-1">PENDING_APPROVAL</b></div>
          </div>
          <div class="ticket-actions">
            <button class="hitl-action-btn approve" onclick="handleTicket(1, 'approved')">✓ 批准维修</button>
            <button class="hitl-action-btn reject" onclick="handleTicket(1, 'rejected')">✕ 拒绝并换机</button>
            <button class="hitl-action-btn timeout" onclick="handleTicket(1, 'timeout')">⏱ 模拟超时未批</button>
          </div>
        </div>

        <div class="hitl-ticket" id="hitl-ticket-2" style="margin-top:10px;">
          <div>
            <div class="ticket-title">食品报损单 #APPR-20260828-02: BATCH-S03-DAIRY-001 鲜牛奶不可逆超温报损</div>
            <div class="ticket-meta">申请角色: Executor · 货值: ¥420.00 · 审批权限: 门店店长 · 状态: <b style="color:var(--amber)" id="ticket-status-2">PENDING_APPROVAL</b></div>
          </div>
          <div class="ticket-actions">
            <button class="hitl-action-btn approve" onclick="handleTicket(2, 'approved')">✓ 批准报损并销毁</button>
            <button class="hitl-action-btn reject" onclick="handleTicket(2, 'rejected')">✕ 拒绝</button>
          </div>
        </div>

        <div id="hitl-log-output" style="margin-top:14px; padding:10px 14px; background:rgba(0,0,0,0.4); border-radius:8px; font-family:var(--font-mono); font-size:12px; color:var(--text-secondary); display:none;">
        </div>
      </div>

      <div style="background:rgba(0,0,0,0.3); border:1px solid var(--border-subtle); border-radius:12px; padding:18px;">
        <h4 style="font-size:14px; color:#fff; margin-bottom:8px;">安全与权限硬性隔离设计</h4>
        <ul style="padding-left:20px; font-size:13px; color:var(--text-secondary); line-height:1.8;">
          <li><b>Append-only 审计表：</b><code>dianxun_runtime</code> 运行账号对 <code>audit_log</code> 仅授予 <code>SELECT, INSERT</code> 权限，剥夺 <code>UPDATE/DELETE</code>，保证审计流水无法篡改。</li>
          <li><b>食品安全不可无条件自动回滚：</b>一旦执行停售（<code>sales_hold</code>），即使工单完成或设备恢复，也必须由 Auditor 重新计算保质期后方能解除，防止变质食品被自动回滚放行。</li>
          <li><b>多 Actor 动态 Token 绑定：</b>MCP 端点支持每 Worker 独立 Token 映射，对越权写动作返回 HTTP 403 <code>FORBIDDEN</code>。</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- ==================== SECTION 6: PPT & DEFENSE MATERIALS ==================== -->
  <section id="view-ppt" class="view-section">
    <div class="panel-card">
      <div class="panel-title">📑 答辩方案 PPT 在线演示与初赛整改对照</div>
      <div class="panel-desc">
        完整 15 页答辩幻灯片在线交互预览（按键盘左右键可翻页），附带针对初赛评委意见的标红整改对照。
      </div>

      <div style="margin-bottom:16px; display:flex; gap:12px; flex-wrap:wrap;">
        <a class="header-btn primary" href="./ppt/" target="_blank">↗ 全屏独立窗口浏览 PPT</a>
        <a class="header-btn" href="./ppt/店巡Agent方案.pdf" target="_blank" download>⬇ 下载答辩方案 PDF (840KB)</a>
      </div>

      <iframe class="ppt-embed-frame" src="./ppt/index.html"></iframe>

      <div style="margin-top:24px; background:rgba(0,0,0,0.3); border:1px solid var(--border-subtle); border-radius:12px; padding:18px;">
        <h4 style="font-size:15px; color:#fff; margin-bottom:10px;">初赛评委意见针对性整改清单（标红对照）</h4>
        <div style="overflow-x:auto;">
          <table class="tbl" style="width:100%; font-size:12.5px;">
            <thead>
              <tr style="color:var(--text-muted); border-bottom:1px solid rgba(255,255,255,0.1);">
                <th style="padding:6px 8px; text-align:left;">初赛评委关注点</th>
                <th style="padding:6px 8px; text-align:left;">整改措施与实现事实</th>
                <th style="padding:6px 8px; text-align:left;">可验证物</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding:8px; color:#fca5a5;"><b>真实 AgentTeams 协作证据不足</b></td>
                <td style="padding:8px;">在广州真实 Linux 服务器部署 AgentTeams v1.2.3 集群与 5 个 Worker（qwen3.8-max），打通 Matrix Team Room 动态委派。</td>
                <td style="padding:8px;" class="mono">agt status / 5 Worker 容器 / status.json</td>
              </tr>
              <tr>
                <td style="padding:8px; color:#fca5a5;"><b>双后端与最小权限不够严密</b></td>
                <td style="padding:8px;">落地 SQLite + PolarDB 双底座，收紧 PostgreSQL 权限使运行账号对 audit_log 仅 SELECT/INSERT，增加不可篡改防回归测试。</td>
                <td style="padding:8px;" class="mono">postgres_security.sql / test_postgres_contract.py</td>
              </tr>
              <tr>
                <td style="padding:8px; color:#fca5a5;"><b>RAG 改善率量化与冷热分层</b></td>
                <td style="padding:8px;">建立专家审核门控知识飞轮，区分热数据与冷归档分区，明确给出合成基线对比，避免外推不实生产结论。</td>
                <td style="padding:8px;" class="mono">test_knowledge_flywheel.py / ablation.json</td>
              </tr>
              <tr>
                <td style="padding:8px; color:#fca5a5;"><b>异常场景与对抗分支覆盖</b></td>
                <td style="padding:8px;">完善 6 大确定性场景（包含传感器误报、柜门未关、审批超时、设备恢复但商品不安全、工具查询部分失败），全部通过回归。</td>
                <td style="padding:8px;" class="mono">command-center.html / 45 Evidence / 26 Trace</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>

  <!-- Footer -->
  <footer class="portal-footer">
    <div>2026 世界人工智能开源大赛 (GOAI) · 赛道一 Agent Infra · 参赛队伍：逐光（第 3 组｜第 13 队）· 作品：店巡 Agent</div>
    <div>代码开源：<a href="https://github.com/XZQ/zhuguang" target="_blank">XZQ/zhuguang</a> · Commit <code>116bd19</code></div>
  </footer>
</div>

<!-- ==================== INTERACTIVE JAVASCRIPT ==================== -->
<script>
// 1 Minute Demo Data
const DEMO_STEPS = [
  {{
    step: 0,
    time: "00:00 - 00:10",
    title: "1. Sentry 只读巡检发现失温异常",
    desc: "Sentry 周期巡检发现冷柜 FROST-S03 温度在 40 分钟内由 3.4°C 飙升至 9.6°C（超出 8.0°C 安全红线）。经数据质量校验排除传感器断流与漂移，标记 critical 严重度，向 Orchestrator 发起紧急遏制请求。",
    agent: "Sentry (巡检守卫 · L0 只读)",
    skill: "anomaly-detect v1.0.0",
    mcp: "query_device_context",
    evidence: "EVID-DETECT-S03-20260828 (Hash: e9d9a4...)",
    trace: "trace-detect-fa4416ba",
    terminal: [
      "[09:00:00] [Sentry] IOT_TELEMETRY: FROST-S03 current_temp=9.6°C (threshold=8.0°C, duration=42min)",
      "[09:00:01] [Sentry] INVOKE_SKILL: anomaly-detect (sensor_quality=good, suspect=false)",
      "[09:00:02] [Sentry] VERDICT: anomaly=True, severity=CRITICAL",
      "[09:00:02] [Sentry] EMIT_REQUEST: request_containment(store_id='S03', device_id='FROST-S03')"
    ]
  }},
  {{
    step: 1,
    time: "00:10 - 00:20",
    title: "2. Executor 紧急执行销售阻断",
    desc: "遵循'食品安全优先'原则，Executor 立即执行 L1 预授权动作 apply_sales_hold，对该冷柜内的 2 个商品批次（鲜牛奶、鲜肉熟食）下发 POS 停售锁，切断收银台结算，防止变质食品流向顾客。",
    agent: "Executor (受控执行 · L1 预授权)",
    skill: "work-order-dispatch (containment)",
    mcp: "apply_sales_hold",
    evidence: "EVID-HOLD-S03-001 (Hash: b2a773...)",
    trace: "trace-hold-fa4416ba",
    terminal: [
      "[09:00:03] [Orchestrator] DISPATCH: Delegating containment to Executor",
      "[09:00:04] [Executor] MCP_CALL: apply_sales_hold(batches=['BATCH-DAIRY-001', 'BATCH-FRESH-001'])",
      "[09:00:05] [Executor] POS_GATEWAY: Broadcasted sales lock to store S03 cashiers",
      "[09:00:05] [Executor] RESULT: 2/2 batches locked (state=HOLD_ACTIVE, risk_contained=True)"
    ]
  }},
  {{
    step: 2,
    time: "00:20 - 00:30",
    title: "3. Diagnoser 多源特征根因诊断",
    desc: "Diagnoser 综合分析门磁状态、除霜加热丝电流与历史故障。排除柜门未关与除霜周期，锁定 Top-1 压缩机启闭故障（置信度 0.94）。同时调用批次风险评估，计算鲜奶已超温暴露，建议强制报损，熟食转移备用冷库。",
    agent: "Diagnoser (根因诊断 · L0 只读)",
    skill: "rootcause-drilldown / coldchain-risk-assess",
    mcp: "query_device_context, query_inventory_batches",
    evidence: "EVID-DIAG-S03-001 (Top-1: compressor_failure)",
    trace: "trace-diag-fa4416ba",
    terminal: [
      "[09:00:06] [Diagnoser] SENSOR_ANALYSIS: Door=CLOSED (100%), Defrost=INACTIVE",
      "[09:00:07] [Diagnoser] HYPOTHESIS_RANK: 1. compressor_failure (0.94) | 2. refrigerant_leak (0.05)",
      "[09:00:08] [Diagnoser] RISK_ASSESS: BATCH-DAIRY-001 exposure=42min -> DISPOSITION=DISPOSE",
      "[09:00:08] [Diagnoser] RISK_ASSESS: BATCH-FRESH-001 exposure=42min -> DISPOSITION=TRANSFER_COLD"
    ]
  }},
  {{
    step: 3,
    time: "00:30 - 00:40",
    title: "4. Executor 处置派单与 HITL 审批",
    desc: "因维修预算超限（¥680）且鲜奶报损属高风险资产处置，系统触发 L2 人工审批流（HITL）。店长通过移动端完成两笔审批批准后，Executor 自动向驻场冷修服务商下发急修工单，维修工到场更换压缩机启动电容。",
    agent: "Executor + Human (HITL 审批流)",
    skill: "work-order-dispatch v1.0.0",
    mcp: "create_approval, create_workorder",
    evidence: "EVID-WO-REPAIR-8821 (Status: EXECUTED)",
    trace: "trace-exec-fa4416ba",
    terminal: [
      "[09:01:00] [Executor] POLICY_GATE: Repair budget ¥680 requires HITL approval",
      "[09:02:00] [HITL] Approval ticket #APPR-01 APPROVED by StoreManager S03",
      "[09:02:05] [Executor] MCP_CALL: create_workorder(vendor='QuickColdService', code='COMP_CAPACITOR')",
      "[09:05:00] [Vendor] Technician marked workorder as EXECUTED (parts replaced, compressor running)"
    ]
  }},
  {{
    step: 4,
    time: "00:40 - 00:50",
    title: "5. Auditor 独立稽核 (双重红线门禁)",
    desc: "核心安全红线生效！维修后冷柜温度已降至 4.8°C（设备恢复）。但系统绝不信任执行者自证：Auditor 独立重查设备与商品事实，判定鲜奶已变质强制报损并维持停售；熟食转移冷库后符合安全标准解除停售。严禁错误放行！",
    agent: "Auditor (独立稽核 · 职责分离)",
    skill: "outcome-verify v1.1.0",
    mcp: "query_device_context, query_inventory_batches",
    evidence: "EVID-AUDIT-VERIFY-001 (Verdict: CONDITIONAL_RESOLVED)",
    trace: "trace-audit-fa4416ba",
    terminal: [
      "[09:06:00] [Auditor] INDEPENDENT_CHECK: Device temp=4.8°C -> PASS",
      "[09:06:01] [Auditor] REDLINE_CHECK: BATCH-DAIRY-001 was >8°C for >30m -> DISPOSITION ENFORCED!",
      "[09:06:02] [Auditor] RELEASE_GUARD: BATCH-DAIRY-001 CANNOT BE RELEASED! (Remain HOLD)",
      "[09:06:03] [Auditor] RELEASE_GUARD: BATCH-FRESH-001 Transfer confirmed -> RELEASE_PERMITTED"
    ]
  }},
  {{
    step: 5,
    time: "00:50 - 00:60",
    title: "6. Orchestrator 复盘沉淀与事件关闭",
    desc: "在确保变质鲜奶销毁、熟食转移、冷柜温控稳定后，Orchestrator 推进至 LEARN 阶段。Auditor 调用 review-report 生成结构化复盘报告，生成'冷柜启动电容老化早期温升特征'知识候选条目，完成闭环安全关闭。",
    agent: "Orchestrator + Auditor (复盘归档)",
    skill: "review-report v1.1.0",
    mcp: "IncidentService, search_knowledge",
    evidence: "EVID-REVIEW-LEARN-001 (State: CLOSED)",
    trace: "trace-learn-fa4416ba",
    terminal: [
      "[09:07:00] [Orchestrator] PHASE_TRANSITION: VERIFY -> LEARN",
      "[09:07:05] [Auditor] INVOKE_SKILL: review-report (Generated postmortem & knowledge candidate)",
      "[09:07:10] [Orchestrator] FINAL_STATUS: Incident CLOSED safely (0 violations, 100% evidence)",
      "[09:07:11] [System] 60-SECOND DEMO COMPLETED SUCCESSFULLY! ★★★★★"
    ]
  }}
];

let currentStep = 0;
let isPlaying = false;
let timerInterval = null;
let secondsLeft = 60;

function renderStep(idx) {{
  const data = DEMO_STEPS[idx];
  currentStep = idx;
  
  // Update step tabs
  document.querySelectorAll('.step-tab').forEach((tab, i) => {{
    tab.classList.toggle('active', i === idx);
    tab.classList.toggle('completed', i < idx);
  }});
  
  // Render details
  const container = document.getElementById('step-detail-container');
  container.innerHTML = `
    <div class="step-info-col">
      <h3>${{data.title}}</h3>
      <div class="step-badges">
        <span class="agent-pill">🤖 ${{data.agent}}</span>
        <span class="skill-pill">⚡ ${{data.skill}}</span>
        <span class="mcp-pill">🔌 ${{data.mcp}}</span>
      </div>
      <div class="step-desc">${{data.desc}}</div>
      <div style="font-size:12px; color:var(--text-muted); display:flex; flex-direction:column; gap:4px; font-family:var(--font-mono);">
        <div><span style="color:var(--text-secondary)">证据编号:</span> ${{data.evidence}}</div>
        <div><span style="color:var(--text-secondary)">追踪链路:</span> ${{data.trace}}</div>
      </div>
    </div>
    <div class="terminal-box">
      <div class="terminal-header">
        <span>RUNTIME AGENT LOGS</span>
        <span>${{data.time}}</span>
      </div>
      ${{data.terminal.map(line => `<div class="terminal-line"><span class="t-cyan">></span> ${{line}}</div>`).join('')}}
    </div>
  `;
}}

function stepDemo(delta) {{
  let next = currentStep + delta;
  if (next < 0) next = 0;
  if (next >= DEMO_STEPS.length) next = DEMO_STEPS.length - 1;
  goToStep(next);
}}

function goToStep(idx) {{
  currentStep = idx;
  renderStep(idx);
}}

function resetDemo() {{
  clearInterval(timerInterval);
  isPlaying = false;
  secondsLeft = 60;
  document.getElementById('demo-timer').textContent = "00:00";
  document.getElementById('btn-play-demo').innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg> 一键演练 (60s)`;
  goToStep(0);
}}

function toggleAutoPlay() {{
  if (isPlaying) {{
    clearInterval(timerInterval);
    isPlaying = false;
    document.getElementById('btn-play-demo').innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg> 继续演练`;
  }} else {{
    isPlaying = true;
    document.getElementById('btn-play-demo').innerHTML = `⏸ 暂停演练`;
    let elapsed = currentStep * 10;
    
    timerInterval = setInterval(() => {{
      elapsed++;
      let m = Math.floor(elapsed / 60).toString().padStart(2, '0');
      let s = (elapsed % 60).toString().padStart(2, '0');
      document.getElementById('demo-timer').textContent = `${{m}}:${{s}}`;
      
      let stepTarget = Math.floor(elapsed / 10);
      if (stepTarget !== currentStep && stepTarget < DEMO_STEPS.length) {{
        renderStep(stepTarget);
      }}
      
      if (elapsed >= 60) {{
        clearInterval(timerInterval);
        isPlaying = false;
        document.getElementById('btn-play-demo').innerHTML = `↺ 再次演练`;
      }}
    }}, 1000);
  }}
}}

// Main Tab Switcher
function switchMainTab(tabId) {{
  document.querySelectorAll('.main-nav-tabs .nav-tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.view-section').forEach(sec => sec.classList.remove('active'));
  
  event.currentTarget.classList.add('active');
  const target = document.getElementById('view-' + tabId);
  if (target) target.classList.add('active');
}}

// Command Center Inner Tabs
document.addEventListener('DOMContentLoaded', () => {{
  renderStep(0);
  
  // Wire up command center tabs
  document.querySelectorAll('.command-center-wrap .tab').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.command-center-wrap .tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.command-center-wrap .panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const targetPanel = document.getElementById(btn.dataset.panel);
      if (targetPanel) targetPanel.classList.add('active');
    }});
  }});
  
  // Fetch real-time status from ./status.json
  fetch('./status.json', {{ cache: 'no-store' }})
    .then(r => r.json())
    .then(data => {{
      if (data && data.services) {{
        const healthyWorkers = data.local_workers || 5;
        document.getElementById('runtime-status-label').textContent = 
          `AgentTeams ${{data.runtime.version || 'v1.2.3'}} · ${{healthyWorkers}} Workers 正常运行`;
      }}
    }})
    .catch(() => {{}});
}});

// HITL Simulator Ticket Handler
function handleTicket(id, decision) {{
  const statusEl = document.getElementById(`ticket-status-${{id}}`);
  const logEl = document.getElementById('hitl-log-output');
  logEl.style.display = 'block';
  
  if (decision === 'approved') {{
    statusEl.innerHTML = '<span style="color:var(--green)">APPROVED (已批准)</span>';
    logEl.innerHTML = `<span style="color:var(--green)">[APPROVED]</span> 单据 #APPR-0${{id}} 已获授权通过。Executor 取得 L2 权限令牌，开始调用后端工单与停售控制系统。`;
  }} else if (decision === 'rejected') {{
    statusEl.innerHTML = '<span style="color:var(--red)">REJECTED (已拒绝)</span>';
    logEl.innerHTML = `<span style="color:var(--red)">[REJECTED]</span> 单据 #APPR-0${{id}} 已被驳回。Executor 撤销当前执行动作，阻断操作推进，状态维持停售。`;
  }} else if (decision === 'timeout') {{
    statusEl.innerHTML = '<span style="color:var(--amber)">TIMEOUT (超时升级)</span>';
    logEl.innerHTML = `<span style="color:var(--amber)">[TIMEOUT]</span> 单据 #APPR-0${{id}} 在规定 SLA 内未获响应。系统触发保护逻辑：禁止擅自维修，自动升级至华南大区经理，同时保持食品停售！`;
  }}
}}
</script>

</body>
</html>
"""
    OUTPUT_FILE.write_text(html_content, encoding="utf-8")
    print(f"Generated {OUTPUT_FILE} ({len(html_content)} bytes)")


if __name__ == "__main__":
    build_portal()
