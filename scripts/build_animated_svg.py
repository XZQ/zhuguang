#!/usr/bin/env python3
"""Generate an animated SVG architecture diagram suitable for GitHub README rendering."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "docs" / "assets"
OUTPUT_SVG = OUTPUT_DIR / "architecture-flow.svg"

SVG_CONTENT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 480" width="100%" height="100%">
  <defs>
    <style>
      @keyframes dashMove {
        from { stroke-dashoffset: 24; }
        to { stroke-dashoffset: 0; }
      }
      @keyframes redlineDash {
        from { stroke-dashoffset: 24; }
        to { stroke-dashoffset: 0; }
      }
      @keyframes redlineGlow {
        0%, 100% { stroke: #ef4444; filter: drop-shadow(0 0 3px #ef4444); }
        50% { stroke: #f87171; filter: drop-shadow(0 0 10px #ef4444); }
      }
      @keyframes nodeGlow {
        0%, 100% { filter: drop-shadow(0 0 4px rgba(56, 189, 248, 0.3)); }
        50% { filter: drop-shadow(0 0 10px rgba(56, 189, 248, 0.7)); }
      }
      .bg-rect { fill: #070d18; }
      .flow-cyan {
        stroke: #38bdf8;
        stroke-width: 1.8;
        stroke-dasharray: 6, 6;
        animation: dashMove 1.2s linear infinite;
        opacity: 0.85;
      }
      .flow-amber {
        stroke: #f59e0b;
        stroke-width: 1.8;
        stroke-dasharray: 5, 5;
        animation: dashMove 1.2s linear infinite;
        opacity: 0.85;
      }
      .flow-redline {
        stroke-width: 2.2;
        stroke-dasharray: 6, 4;
        animation: redlineDash 1s linear infinite, redlineGlow 2s ease-in-out infinite;
      }
      .card-orch {
        animation: nodeGlow 3s ease-in-out infinite;
      }
      .card-core {
        animation: nodeGlow 2.5s ease-in-out infinite;
      }
      text {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", Helvetica, Arial, sans-serif;
      }
      .mono {
        font-family: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
      }
    </style>

    <!-- Gradients -->
    <linearGradient id="g-orch" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
    <linearGradient id="g-core" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0284c7"/>
      <stop offset="100%" stop-color="#034d75"/>
    </linearGradient>
    <linearGradient id="g-guard" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#78350f"/>
      <stop offset="100%" stop-color="#451a03"/>
    </linearGradient>
    <linearGradient id="g-worker" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>

    <!-- Arrow Markers -->
    <marker id="m-cyan" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#38bdf8"/>
    </marker>
    <marker id="m-amber" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#f59e0b"/>
    </marker>
    <marker id="m-red" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#ef4444"/>
    </marker>
  </defs>

  <!-- Background Canvas -->
  <rect width="940" height="480" rx="16" class="bg-rect" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Background Grid Dots -->
  <g opacity="0.1" fill="#38bdf8">
    <circle cx="60" cy="60" r="1.5"/><circle cx="140" cy="60" r="1.5"/><circle cx="220" cy="60" r="1.5"/><circle cx="300" cy="60" r="1.5"/>
    <circle cx="380" cy="60" r="1.5"/><circle cx="460" cy="60" r="1.5"/><circle cx="540" cy="60" r="1.5"/><circle cx="620" cy="60" r="1.5"/>
    <circle cx="700" cy="60" r="1.5"/><circle cx="780" cy="60" r="1.5"/><circle cx="860" cy="60" r="1.5"/>
    <circle cx="60" cy="420" r="1.5"/><circle cx="140" cy="420" r="1.5"/><circle cx="220" cy="420" r="1.5"/><circle cx="300" cy="420" r="1.5"/>
    <circle cx="780" cy="420" r="1.5"/><circle cx="860" cy="420" r="1.5"/>
  </g>

  <!-- Title & Subtitle Badge -->
  <g transform="translate(24, 28)">
    <rect x="0" y="0" width="56" height="20" rx="4" fill="#0284c7" opacity="0.9"/>
    <text x="28" y="14" fill="#ffffff" font-size="10.5" font-weight="800" text-anchor="middle">逐光队</text>
    <text x="66" y="15" fill="#f1f5f9" font-size="14.5" font-weight="700">店巡 Agent · 多 Agent 闭环架构动态流向</text>
    <text x="450" y="14" fill="#64748b" font-size="11">AgentTeams v1.2.3 · 5 Workers 职责分离 · 双重状态安全闭环</text>
  </g>

  <!-- ================= CONNECTION PATHS ================= -->
  <g id="paths">
    <!-- Input -> Orchestrator -->
    <path id="p-in-orch" d="M 120 230 L 190 230" fill="none" class="flow-cyan" marker-end="url(#m-cyan)"/>

    <!-- Orchestrator -> 4 Workers -->
    <path id="p-orch-sen" d="M 310 210 C 340 210, 350 90, 400 90" fill="none" class="flow-cyan" marker-end="url(#m-cyan)"/>
    <path id="p-orch-dia" d="M 310 220 C 345 220, 350 180, 400 180" fill="none" class="flow-cyan" marker-end="url(#m-cyan)"/>
    <path id="p-orch-exe" d="M 310 240 C 345 240, 350 280, 400 280" fill="none" class="flow-cyan" marker-end="url(#m-cyan)"/>
    <path id="p-orch-aud" d="M 310 250 C 340 250, 350 370, 400 370" fill="none" class="flow-cyan" marker-end="url(#m-cyan)"/>

    <!-- 4 Workers -> IncidentService (Core) -->
    <path id="p-sen-core" d="M 540 90 C 590 90, 600 210, 640 210" fill="none" class="flow-cyan" marker-end="url(#m-cyan)"/>
    <path id="p-dia-core" d="M 540 180 C 585 180, 595 220, 640 225" fill="none" class="flow-cyan" marker-end="url(#m-cyan)"/>
    <path id="p-exe-core" d="M 540 280 C 585 280, 595 240, 640 235" fill="none" class="flow-cyan" marker-end="url(#m-cyan)"/>
    <path id="p-aud-core" d="M 540 370 C 590 370, 600 250, 640 250" fill="none" class="flow-cyan" marker-end="url(#m-cyan)"/>

    <!-- Core <--> MCP -->
    <path id="p-core-mcp" d="M 770 220 L 810 220" fill="none" class="flow-cyan" marker-end="url(#m-cyan)"/>
    <path id="p-mcp-core" d="M 810 240 L 770 240" fill="none" class="flow-cyan" marker-end="url(#m-cyan)"/>

    <!-- Guard (Policy/Approval) -.约束.-> Executor -->
    <path id="p-guard-exe" d="M 470 430 L 470 315" fill="none" class="flow-amber" marker-end="url(#m-amber)"/>

    <!-- Auditor -.未通过阻断关闭或回开.-> Core (REDLINE) -->
    <path id="p-aud-block" d="M 470 395 C 470 435, 700 435, 705 270" fill="none" class="flow-redline" marker-end="url(#m-red)"/>
  </g>

  <!-- ================= ANIMATED FLYING DATA PACKETS (Native SVG SMIL) ================= -->
  <g id="particles">
    <!-- Input to Orchestrator -->
    <circle r="3.5" fill="#38bdf8">
      <animateMotion dur="2.2s" repeatCount="indefinite" path="M 120 230 L 190 230" />
    </circle>

    <!-- Orchestrator to Sentry -->
    <circle r="3.5" fill="#38bdf8">
      <animateMotion dur="2.8s" repeatCount="indefinite" path="M 310 210 C 340 210, 350 90, 400 90" />
    </circle>
    <!-- Orchestrator to Diagnoser -->
    <circle r="3.5" fill="#38bdf8">
      <animateMotion dur="2.8s" begin="0.7s" repeatCount="indefinite" path="M 310 220 C 345 220, 350 180, 400 180" />
    </circle>
    <!-- Orchestrator to Executor -->
    <circle r="3.5" fill="#38bdf8">
      <animateMotion dur="2.8s" begin="1.4s" repeatCount="indefinite" path="M 310 240 C 345 240, 350 280, 400 280" />
    </circle>
    <!-- Orchestrator to Auditor -->
    <circle r="3.5" fill="#38bdf8">
      <animateMotion dur="2.8s" begin="2.1s" repeatCount="indefinite" path="M 310 250 C 340 250, 350 370, 400 370" />
    </circle>

    <!-- Workers to Core -->
    <circle r="3.5" fill="#38bdf8">
      <animateMotion dur="2.6s" begin="0.3s" repeatCount="indefinite" path="M 540 90 C 590 90, 600 210, 640 210" />
    </circle>
    <circle r="3.5" fill="#38bdf8">
      <animateMotion dur="2.6s" begin="1.1s" repeatCount="indefinite" path="M 540 180 C 585 180, 595 220, 640 225" />
    </circle>
    <circle r="3.5" fill="#38bdf8">
      <animateMotion dur="2.6s" begin="1.8s" repeatCount="indefinite" path="M 540 280 C 585 280, 595 240, 640 235" />
    </circle>
    <circle r="3.5" fill="#38bdf8">
      <animateMotion dur="2.6s" begin="2.4s" repeatCount="indefinite" path="M 540 370 C 590 370, 600 250, 640 250" />
    </circle>

    <!-- Core <--> MCP -->
    <circle r="3.5" fill="#38bdf8">
      <animateMotion dur="2.0s" repeatCount="indefinite" path="M 770 220 L 810 220" />
    </circle>
    <circle r="3.5" fill="#7dd3fc">
      <animateMotion dur="2.0s" begin="1.0s" repeatCount="indefinite" path="M 810 240 L 770 240" />
    </circle>

    <!-- Guard to Executor -->
    <circle r="3.5" fill="#f59e0b">
      <animateMotion dur="2.4s" repeatCount="indefinite" path="M 470 430 L 470 315" />
    </circle>

    <!-- Auditor Redline Blocker Pulse -->
    <circle r="4" fill="#ef4444">
      <animateMotion dur="2.5s" repeatCount="indefinite" path="M 470 395 C 470 435, 700 435, 705 270" />
    </circle>
  </g>

  <!-- ================= ANNOTATIONS ================= -->
  <!-- Redline Banner -->
  <g transform="translate(540, 440)">
    <rect x="-10" y="-12" width="220" height="24" rx="6" fill="#450a0a" stroke="#ef4444" stroke-width="1.2"/>
    <text x="100" y="4.5" fill="#fca5a5" font-size="11" font-weight="700" text-anchor="middle">
      ⚠ 未通过则阻断关闭或回开 (核心红线)
    </text>
  </g>

  <!-- Guard Label -->
  <g transform="translate(395, 325)">
    <text x="75" y="24" fill="#fcd34d" font-size="10.5" font-weight="600" text-anchor="middle">
      约束写权限
    </text>
  </g>

  <!-- ================= NODES ================= -->

  <!-- Node 1: Input -->
  <g id="node-input" transform="translate(20, 195)">
    <rect width="100" height="70" rx="10" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>
    <text x="50" y="32" fill="#94a3b8" font-size="11" font-weight="600" text-anchor="middle">事件源触发</text>
    <text x="50" y="52" fill="#38bdf8" font-size="13" font-weight="700" text-anchor="middle">异常 / 巡检任务</text>
  </g>

  <!-- Node 2: Orchestrator -->
  <g id="node-orch" class="card-orch" transform="translate(190, 185)">
    <rect width="120" height="90" rx="12" fill="url(#g-orch)" stroke="#38bdf8" stroke-width="2"/>
    <rect x="25" y="-10" width="70" height="20" rx="5" fill="#0284c7"/>
    <text x="60" y="4" fill="#ffffff" font-size="9.5" font-weight="800" text-anchor="middle">TEAM LEADER</text>
    <text x="60" y="38" fill="#ffffff" font-size="14" font-weight="700" text-anchor="middle">Orchestrator</text>
    <text x="60" y="58" fill="#94a3b8" font-size="11" text-anchor="middle">任务拆解与汇总</text>
    <text x="60" y="74" fill="#38bdf8" font-size="10" class="mono" text-anchor="middle">qwen3.8-max</text>
  </g>

  <!-- Node 3: Sentry (Worker 1) -->
  <g id="node-sentry" transform="translate(400, 55)">
    <rect width="140" height="68" rx="10" fill="url(#g-worker)" stroke="#475569" stroke-width="1.5"/>
    <text x="70" y="26" fill="#38bdf8" font-size="13" font-weight="700" text-anchor="middle">Sentry (巡检守卫)</text>
    <text x="70" y="44" fill="#94a3b8" font-size="11" text-anchor="middle">失温检测 · 质量校验</text>
    <text x="70" y="59" fill="#10b981" font-size="10" class="mono" text-anchor="middle">L0 只读 · 遏制请求</text>
  </g>

  <!-- Node 4: Diagnoser (Worker 2) -->
  <g id="node-diag" transform="translate(400, 145)">
    <rect width="140" height="68" rx="10" fill="url(#g-worker)" stroke="#475569" stroke-width="1.5"/>
    <text x="70" y="26" fill="#38bdf8" font-size="13" font-weight="700" text-anchor="middle">Diagnoser (根因诊断)</text>
    <text x="70" y="44" fill="#94a3b8" font-size="11" text-anchor="middle">多源假设 · 批次暴露</text>
    <text x="70" y="59" fill="#10b981" font-size="10" class="mono" text-anchor="middle">L0 只读 · Top-K 排序</text>
  </g>

  <!-- Node 5: Executor (Worker 3) -->
  <g id="node-exec" transform="translate(400, 245)">
    <rect width="140" height="70" rx="10" fill="url(#g-worker)" stroke="#f59e0b" stroke-width="1.5"/>
    <text x="70" y="26" fill="#fcd34d" font-size="13" font-weight="700" text-anchor="middle">Executor (受控执行)</text>
    <text x="70" y="44" fill="#94a3b8" font-size="11" text-anchor="middle">停售隔离 · 派发工单</text>
    <text x="70" y="60" fill="#f59e0b" font-size="10" class="mono" text-anchor="middle">L1/L2 受控写 · 幂等执行</text>
  </g>

  <!-- Node 6: Auditor (Worker 4) -->
  <g id="node-audit" transform="translate(400, 335)">
    <rect width="140" height="70" rx="10" fill="url(#g-worker)" stroke="#ef4444" stroke-width="1.8"/>
    <text x="70" y="26" fill="#fca5a5" font-size="13" font-weight="700" text-anchor="middle">Auditor (独立稽核)</text>
    <text x="70" y="44" fill="#cbd5e1" font-size="11" text-anchor="middle">独立重查事实 · 放行门禁</text>
    <text x="70" y="60" fill="#ef4444" font-size="10" class="mono" text-anchor="middle">核心红线：严禁自验</text>
  </g>

  <!-- Node 7: Guard (Policy/Approval/Audit) -->
  <g id="node-guard" transform="translate(370, 420)">
    <rect width="200" height="52" rx="8" fill="url(#g-guard)" stroke="#f59e0b" stroke-width="1.5"/>
    <text x="100" y="22" fill="#fbbf24" font-size="11.5" font-weight="700" text-anchor="middle">业务角色 · Policy / 人工审批</text>
    <text x="100" y="40" fill="#fef08a" font-size="10" class="mono" text-anchor="middle">幂等校验 · Append-only 审计</text>
  </g>

  <!-- Node 8: IncidentService (Central Core) -->
  <g id="node-core" class="card-core" transform="translate(640, 185)">
    <rect width="130" height="90" rx="12" fill="url(#g-core)" stroke="#38bdf8" stroke-width="2"/>
    <text x="65" y="30" fill="#ffffff" font-size="13" font-weight="800" text-anchor="middle">IncidentService</text>
    <text x="65" y="48" fill="#bae6fd" font-size="11" font-weight="600" text-anchor="middle">唯一业务事实入口</text>
    <text x="65" y="68" fill="#7dd3fc" font-size="10" text-anchor="middle">五阶段状态机</text>
    <text x="65" y="82" fill="#38bdf8" font-size="9.5" class="mono" text-anchor="middle">SQLite / PolarDB</text>
  </g>

  <!-- Node 9: 12 MCP Tools -->
  <g id="node-mcp" transform="translate(810, 190)">
    <rect width="115" height="80" rx="10" fill="#0f172a" stroke="#475569" stroke-width="1.5"/>
    <text x="57" y="28" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">12 个 P0 MCP</text>
    <text x="57" y="46" fill="#94a3b8" font-size="10.5" text-anchor="middle">设备 · 库存 · 停售</text>
    <text x="57" y="62" fill="#94a3b8" font-size="10.5" text-anchor="middle">审批 · 工单</text>
  </g>
</svg>
"""

def build():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_SVG.write_text(SVG_CONTENT, encoding="utf-8")
    print(f"Generated {OUTPUT_SVG} ({len(SVG_CONTENT)} bytes)")

if __name__ == "__main__":
    build()
