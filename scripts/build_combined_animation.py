#!/usr/bin/env python3
"""Build combined Temperature Monitoring + Agent Architecture animation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "dist" / "delivery-portal" / "architecture-flow.html"
ARTIFACT_FILE = Path("/Users/80371804/.gemini/antigravity/brain/b46ee03a-8a82-4354-b66d-7815347b840c/architecture_flow_animation.html")

HTML_CONTENT = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>店巡 Agent · 实时温度监控与多 Agent 闭环架构联动</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    @keyframes pulseGlow {
      0%, 100% { filter: drop-shadow(0 0 6px rgba(56, 189, 248, 0.4)); }
      50% { filter: drop-shadow(0 0 16px rgba(56, 189, 248, 0.9)); }
    }
    @keyframes dashMove {
      to { stroke-dashoffset: -40; }
    }
    @keyframes redlinePulse {
      0%, 100% { stroke: #ef4444; filter: drop-shadow(0 0 4px rgba(239, 68, 68, 0.5)); }
      50% { stroke: #f87171; filter: drop-shadow(0 0 12px rgba(239, 68, 68, 0.9)); }
    }
    @keyframes beaconBlink {
      0%, 100% { transform: scale(1); opacity: 1; }
      50% { transform: scale(2.2); opacity: 0; }
    }
    .flow-line {
      stroke: rgba(56, 189, 248, 0.35);
      stroke-dasharray: 6, 6;
      animation: dashMove 1.5s linear infinite;
    }
    .flow-line-active {
      stroke: #38bdf8;
      stroke-width: 2.5px;
      stroke-dasharray: 8, 4;
      animation: dashMove 0.8s linear infinite;
      filter: drop-shadow(0 0 6px rgba(56, 189, 248, 0.8));
    }
    .flow-line-guard {
      stroke: #f59e0b;
      stroke-dasharray: 5, 5;
      animation: dashMove 1.2s linear infinite;
    }
    .flow-line-redline {
      animation: redlinePulse 1.8s ease-in-out infinite, dashMove 1.2s linear infinite;
      stroke-dasharray: 6, 4;
      stroke-width: 2.5px;
    }
    .node-box {
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      cursor: pointer;
    }
    .node-box:hover {
      transform: translateY(-2px);
      filter: drop-shadow(0 6px 14px rgba(56, 189, 248, 0.35));
    }
    .node-active {
      animation: pulseGlow 1.8s infinite;
      stroke: #38bdf8 !important;
      stroke-width: 2px !important;
    }
    .temp-pulse-beacon {
      transform-origin: center;
      animation: beaconBlink 1.6s ease-out infinite;
    }
  </style>
</head>
<body class="bg-transparent text-[var(--foreground,#f1f5f9)] antialiased p-2 sm:p-4">
  <div class="bg-[var(--card,#0f172a)] border border-[var(--border,rgba(56,189,248,0.2))] rounded-2xl p-4 sm:p-5 shadow-2xl backdrop-blur-md max-w-5xl mx-auto space-y-4">
    
    <!-- Header & Controls -->
    <div class="flex flex-wrap justify-between items-center gap-3 pb-3 border-b border-[var(--border,rgba(255,255,255,0.1))]">
      <div>
        <div class="flex items-center gap-2">
          <span class="px-2 py-0.5 text-xs font-bold rounded bg-sky-500/20 text-sky-400 border border-sky-500/30">逐光队 · GOAI 赛道一</span>
          <h2 class="text-base sm:text-lg font-bold tracking-tight text-white flex items-center gap-2">
            店巡 Agent · 实时温度监测与 5-Agent 闭环架构联动演示
          </h2>
        </div>
        <p class="text-xs text-slate-400 mt-0.5">
          融合「智感温盾」物联时序监测与 Westgard 质控，驱动五阶段多 Agent 安全闭环
        </p>
      </div>

      <!-- Action Controls -->
      <div class="flex items-center gap-2">
        <button id="btn-play" onclick="togglePlay()" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-sky-600 hover:bg-sky-500 text-white shadow-lg shadow-sky-600/30 transition-all flex items-center gap-1.5">
          <span id="play-icon">▶</span>
          <span id="play-text">自动演练 (60s)</span>
        </button>
        <button onclick="resetFlow()" class="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-all">
          重置
        </button>
        <div class="hidden md:flex bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs">
          <button onclick="setPhase(1)" id="tab-p1" class="phase-btn px-2 py-1 rounded text-slate-400 hover:text-white transition">1.巡检失温</button>
          <button onclick="setPhase(2)" id="tab-p2" class="phase-btn px-2 py-1 rounded text-slate-400 hover:text-white transition">2.停售遏制</button>
          <button onclick="setPhase(3)" id="tab-p3" class="phase-btn px-2 py-1 rounded text-slate-400 hover:text-white transition">3.根因诊断</button>
          <button onclick="setPhase(4)" id="tab-p4" class="phase-btn px-2 py-1 rounded text-slate-400 hover:text-white transition">4.派修降温</button>
          <button onclick="setPhase(5)" id="tab-p5" class="phase-btn px-2 py-1 rounded text-slate-400 hover:text-white transition">5.独立稽核(阻断)</button>
          <button onclick="setPhase(6)" id="tab-p6" class="phase-btn px-2 py-1 rounded text-slate-400 hover:text-white transition">6.安全闭环</button>
        </div>
      </div>
    </div>

    <!-- ================= PANEL 1: LIVE TEMPERATURE MONITOR (智感温盾) ================= -->
    <div class="bg-slate-950/70 border border-slate-800 rounded-xl p-3 sm:p-4">
      <div class="flex flex-wrap justify-between items-center gap-3 mb-3">
        <div class="flex items-center gap-3">
          <span class="px-2 py-0.5 text-[11px] font-bold rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            智感温盾 TEMPGUARD 实时遥测
          </span>
          <span class="text-xs text-slate-300 font-medium">设备：2号冷藏柜（FROST-S03 · A-102室）</span>
        </div>
        <div class="flex items-center gap-4 text-xs font-mono">
          <span class="text-slate-400">安全走廊: <b class="text-emerald-400">2.0°C ~ 8.0°C</b></span>
          <span class="text-slate-400">Westgard质控: <b class="text-amber-400">±3SD (8.5°C)</b></span>
        </div>
      </div>

      <!-- Metric Cards Grid -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3 text-xs">
        <div class="bg-slate-900/90 border border-slate-800 rounded-lg p-2.5">
          <div class="text-slate-400 text-[11px]">当前传感器温度</div>
          <div class="text-xl sm:text-2xl font-black font-mono transition-colors duration-300" id="gauge-temp">3.4°C</div>
          <div class="text-[10px] text-slate-500 mt-0.5" id="gauge-temp-sub">正常平稳</div>
        </div>
        <div class="bg-slate-900/90 border border-slate-800 rounded-lg p-2.5">
          <div class="text-slate-400 text-[11px]">物理设备状态</div>
          <div class="text-base sm:text-lg font-bold font-mono text-emerald-400 mt-0.5" id="gauge-dev-state">NORMAL (制冷正常)</div>
          <div class="text-[10px] text-slate-500 mt-0.5" id="gauge-dev-sub">压缩机运转中</div>
        </div>
        <div class="bg-slate-900/90 border border-slate-800 rounded-lg p-2.5">
          <div class="text-slate-400 text-[11px]">商品批次风险状态</div>
          <div class="text-base sm:text-lg font-bold font-mono text-emerald-400 mt-0.5" id="gauge-goods-state">SAFE (商品安全)</div>
          <div class="text-[10px] text-slate-500 mt-0.5" id="gauge-goods-sub">未超温 · 正常销售</div>
        </div>
        <div class="bg-slate-900/90 border border-slate-800 rounded-lg p-2.5">
          <div class="text-slate-400 text-[11px]">超温暴露积分时长</div>
          <div class="text-xl sm:text-2xl font-black font-mono text-slate-400" id="gauge-exposure">0 min</div>
          <div class="text-[10px] text-slate-500 mt-0.5">允许耐受阈值: 30 min</div>
        </div>
      </div>

      <!-- Animated Temperature Chart SVG -->
      <div class="relative w-full overflow-hidden bg-slate-900/60 rounded-lg border border-slate-800/80 p-2">
        <svg id="temp-svg" viewBox="0 0 900 190" class="w-full h-auto select-none font-mono">
          <defs>
            <linearGradient id="g-safe-band" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#10b981" stop-opacity="0.15"/>
              <stop offset="100%" stop-color="#10b981" stop-opacity="0.02"/>
            </linearGradient>
            <linearGradient id="g-danger-zone" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#ef4444" stop-opacity="0.3"/>
              <stop offset="100%" stop-color="#ef4444" stop-opacity="0.05"/>
            </linearGradient>
            <linearGradient id="g-curve" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#10b981"/>
              <stop offset="35%" stop-color="#f59e0b"/>
              <stop offset="60%" stop-color="#ef4444"/>
              <stop offset="85%" stop-color="#38bdf8"/>
              <stop offset="100%" stop-color="#10b981"/>
            </linearGradient>
          </defs>

          <!-- Safe Temperature Corridor (2.0°C - 8.0°C) -> Y: 130 to 60 -->
          <rect x="70" y="60" width="810" height="70" fill="url(#g-safe-band)" rx="4"/>
          <line x1="70" y1="60" x2="880" y2="60" stroke="#f87171" stroke-width="1.2" stroke-dasharray="4,4"/>
          <text x="885" y="64" fill="#f87171" font-size="10" font-weight="700">8.0°C 告警红线</text>

          <line x1="70" y1="50" x2="880" y2="50" stroke="#fbbf24" stroke-width="1" stroke-dasharray="2,3"/>
          <text x="885" y="53" fill="#fbbf24" font-size="9">Westgard +3SD (8.5°C)</text>

          <line x1="70" y1="130" x2="880" y2="130" stroke="#34d399" stroke-width="1" stroke-dasharray="4,4"/>
          <text x="885" y="134" fill="#34d399" font-size="10">2.0°C 下限</text>

          <line x1="70" y1="105" x2="880" y2="105" stroke="#64748b" stroke-width="0.8" stroke-dasharray="2,4"/>
          <text x="885" y="108" fill="#64748b" font-size="9">均值 Mean (4.2°C)</text>

          <!-- Axes -->
          <line x1="70" y1="20" x2="70" y2="155" stroke="#334155" stroke-width="1"/>
          <line x1="70" y1="155" x2="880" y2="155" stroke="#334155" stroke-width="1"/>

          <!-- Y Axis Labels -->
          <text x="62" y="38" fill="#94a3b8" font-size="10" text-anchor="end">10.0°C</text>
          <text x="62" y="64" fill="#f87171" font-size="10" font-weight="700" text-anchor="end">8.0°C</text>
          <text x="62" y="108" fill="#94a3b8" font-size="10" text-anchor="end">4.0°C</text>
          <text x="62" y="134" fill="#34d399" font-size="10" text-anchor="end">2.0°C</text>

          <!-- X Axis Time Marks -->
          <text x="80" y="172" fill="#64748b" font-size="10">08:20</text>
          <text x="210" y="172" fill="#64748b" font-size="10">08:40</text>
          <text x="350" y="172" fill="#64748b" font-size="10">09:00 (巡检超温)</text>
          <text x="490" y="172" fill="#64748b" font-size="10">09:15 (维修派单)</text>
          <text x="630" y="172" fill="#64748b" font-size="10">09:35 (换件制冷)</text>
          <text x="780" y="172" fill="#64748b" font-size="10">09:50 (Auditor重查)</text>

          <!-- Exposure Fill Area (09:00 to 09:42 above 8°C) -->
          <polygon id="exposure-poly" points="260,60 260,60 630,60 630,60" fill="url(#g-danger-zone)" opacity="0"/>

          <!-- Complete Temperature Curve Path -->
          <!-- Normal 3.4°C(Y:115) -> Spikes at 08:35 to 9.6°C(Y:42) -> Stays high -> Repair at 09:25 -> Drops to 4.8°C(Y:100) -->
          <path id="temp-line" d="M 80 115 Q 160 112, 230 110 T 300 58 T 380 42 T 480 44 T 570 48 Q 620 52, 690 96 T 820 102" fill="none" stroke="url(#g-curve)" stroke-width="2.5"/>

          <!-- Live Progress Cursor & Pulse Beacon -->
          <g id="temp-cursor" transform="translate(80, 115)">
            <circle r="12" fill="#38bdf8" opacity="0.3" class="temp-pulse-beacon"/>
            <circle r="5" fill="#38bdf8" stroke="#ffffff" stroke-width="2"/>
            <rect x="-35" y="-28" width="70" height="20" rx="4" fill="#0f172a" stroke="#38bdf8" stroke-width="1"/>
            <text id="cursor-label" x="0" y="-14" fill="#38bdf8" font-size="10.5" font-weight="700" text-anchor="middle">3.4°C</text>
          </g>

          <!-- Annotation Badges on Chart -->
          <g id="badge-containment" transform="translate(350, 22)" opacity="0">
            <rect width="130" height="20" rx="4" fill="#78350f" stroke="#f59e0b" stroke-width="1"/>
            <text x="65" y="14" fill="#fef08a" font-size="10" font-weight="700" text-anchor="middle">🔒 Executor 停售锁已下发</text>
          </g>

          <g id="badge-redline-block" transform="translate(680, 22)" opacity="0">
            <rect width="165" height="20" rx="4" fill="#450a0a" stroke="#ef4444" stroke-width="1.2"/>
            <text x="82" y="14" fill="#fca5a5" font-size="10" font-weight="700" text-anchor="middle">🛡️ Auditor: 鲜奶超温变质阻断!</text>
          </g>
        </svg>
      </div>
    </div>

    <!-- ================= PANEL 2: 5-AGENT ARCHITECTURE FLOW ================= -->
    <div class="bg-slate-950/70 border border-slate-800 rounded-xl p-3 sm:p-4">
      <div class="flex justify-between items-center mb-2">
        <div class="flex items-center gap-2">
          <span class="text-sky-400 font-bold text-xs">🤖 店巡 Agent · 5 大业务 Worker 协同与安全闭环</span>
        </div>
        <div id="flow-status-text" class="text-xs text-slate-300 font-mono">
          联动状态：<span class="text-sky-400 font-bold" id="stage-name-text">Sentry 巡检待命</span>
        </div>
      </div>

      <!-- SVG Architecture Diagram Canvas -->
      <div class="relative w-full overflow-hidden bg-slate-900/40 rounded-lg border border-slate-800/80 p-1">
        <svg id="arch-svg" viewBox="0 0 940 380" class="w-full h-auto select-none">
          <defs>
            <linearGradient id="grad-orch" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#1e293b"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
            <linearGradient id="grad-core" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0369a1"/><stop offset="100%" stop-color="#0c4a6e"/></linearGradient>
            <linearGradient id="grad-guard" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#78350f"/><stop offset="100%" stop-color="#451a03"/></linearGradient>
            <linearGradient id="grad-worker" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#1e293b"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>

            <marker id="arr-cyan" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 1 L 9 5 L 0 9 z" fill="#38bdf8"/></marker>
            <marker id="arr-amber" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 1 L 9 5 L 0 9 z" fill="#f59e0b"/></marker>
            <marker id="arr-red" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 1 L 9 5 L 0 9 z" fill="#ef4444"/></marker>
          </defs>

          <!-- ================= CONNECTION PATHS ================= -->
          <g id="connections">
            <!-- Telemetry input from TempGuard above -->
            <path id="path-input-orch" d="M 120 180 L 180 180" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>

            <!-- Orchestrator -> 4 Workers -->
            <path id="path-orch-sentry" d="M 290 160 C 330 160, 340 60, 390 60" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-orch-diag" d="M 290 170 C 335 170, 340 135, 390 135" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-orch-exec" d="M 290 190 C 335 190, 340 215, 390 215" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-orch-audit" d="M 290 200 C 330 200, 340 295, 390 295" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>

            <!-- Workers -> IncidentService (Core) -->
            <path id="path-sentry-core" d="M 530 60 C 580 60, 590 160, 630 165" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-diag-core" d="M 530 135 C 575 135, 585 170, 630 175" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-exec-core" d="M 530 215 C 575 215, 585 185, 630 185" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-audit-core" d="M 530 295 C 580 295, 590 195, 630 195" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>

            <!-- Core <--> MCP -->
            <path id="path-core-mcp" d="M 750 175 L 795 175" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-mcp-core" d="M 795 195 L 750 195" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>

            <!-- Guard -.-> Executor -->
            <path id="path-guard-exec" d="M 460 345 L 460 250" fill="none" class="flow-line-guard" marker-end="url(#arr-amber)"/>

            <!-- Auditor Redline Blocker -->
            <path id="path-audit-block" d="M 460 325 C 460 365, 690 365, 695 230" fill="none" class="flow-line-redline" marker-end="url(#arr-red)"/>
          </g>

          <!-- Redline Annotation Label -->
          <g transform="translate(530, 355)">
            <rect x="-10" y="-12" width="220" height="22" rx="5" fill="#450a0a" stroke="#ef4444" stroke-width="1"/>
            <text x="100" y="3" fill="#fca5a5" font-size="10.5" font-weight="700" text-anchor="middle">
              ⚠ 未通过则阻断关闭或回开 (核心红线)
            </text>
          </g>

          <!-- ================= NODES ================= -->
          <!-- Node 1: Input -->
          <g id="node-input" class="node-box" transform="translate(15, 145)">
            <rect width="105" height="70" rx="8" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>
            <text x="52" y="28" fill="#94a3b8" font-size="10.5" font-weight="600" text-anchor="middle">智感温盾遥测</text>
            <text x="52" y="46" fill="#38bdf8" font-size="11.5" font-weight="700" text-anchor="middle">失温时序数据</text>
            <text x="52" y="60" fill="#64748b" font-size="9" text-anchor="middle">Westgard ±3SD</text>
          </g>

          <!-- Node 2: Orchestrator -->
          <g id="node-orch" class="node-box" transform="translate(180, 140)">
            <rect width="110" height="80" rx="10" fill="url(#grad-orch)" stroke="#38bdf8" stroke-width="1.8"/>
            <rect x="20" y="-9" width="70" height="18" rx="4" fill="#0284c7"/>
            <text x="55" y="3" fill="#ffffff" font-size="9" font-weight="800" text-anchor="middle">TEAM LEADER</text>
            <text x="55" y="32" fill="#ffffff" font-size="13" font-weight="700" text-anchor="middle">Orchestrator</text>
            <text x="55" y="49" fill="#94a3b8" font-size="10" text-anchor="middle">任务拆解与汇总</text>
            <text x="55" y="64" fill="#38bdf8" font-size="9.5" font-family="monospace" text-anchor="middle">qwen3.8-max</text>
          </g>

          <!-- Node 3: Sentry -->
          <g id="node-sentry" class="node-box" transform="translate(390, 32)">
            <rect width="140" height="56" rx="8" fill="url(#grad-worker)" stroke="#475569" stroke-width="1.5"/>
            <text x="70" y="22" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">Sentry (巡检守卫)</text>
            <text x="70" y="37" fill="#94a3b8" font-size="10" text-anchor="middle">失温检测 · 质量校验</text>
            <text x="70" y="49" fill="#10b981" font-size="9" font-family="monospace" text-anchor="middle">L0 只读 · 遏制请求</text>
          </g>

          <!-- Node 4: Diagnoser -->
          <g id="node-diag" class="node-box" transform="translate(390, 107)">
            <rect width="140" height="56" rx="8" fill="url(#grad-worker)" stroke="#475569" stroke-width="1.5"/>
            <text x="70" y="22" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">Diagnoser (根因诊断)</text>
            <text x="70" y="37" fill="#94a3b8" font-size="10" text-anchor="middle">多源假设 · 批次暴露</text>
            <text x="70" y="49" fill="#10b981" font-size="9" font-family="monospace" text-anchor="middle">L0 只读 · Top-K 排序</text>
          </g>

          <!-- Node 5: Executor -->
          <g id="node-exec" class="node-box" transform="translate(390, 187)">
            <rect width="140" height="58" rx="8" fill="url(#grad-worker)" stroke="#f59e0b" stroke-width="1.5"/>
            <text x="70" y="22" fill="#fcd34d" font-size="12" font-weight="700" text-anchor="middle">Executor (受控执行)</text>
            <text x="70" y="37" fill="#94a3b8" font-size="10" text-anchor="middle">停售隔离 · 派发工单</text>
            <text x="70" y="50" fill="#f59e0b" font-size="9" font-family="monospace" text-anchor="middle">L1/L2 受控写 · 幂等执行</text>
          </g>

          <!-- Node 6: Auditor -->
          <g id="node-audit" class="node-box" transform="translate(390, 267)">
            <rect width="140" height="58" rx="8" fill="url(#grad-worker)" stroke="#ef4444" stroke-width="1.8"/>
            <text x="70" y="22" fill="#fca5a5" font-size="12" font-weight="700" text-anchor="middle">Auditor (独立稽核)</text>
            <text x="70" y="37" fill="#cbd5e1" font-size="10" text-anchor="middle">独立重查事实 · 放行门禁</text>
            <text x="70" y="50" fill="#ef4444" font-size="9" font-family="monospace" text-anchor="middle">核心红线：严禁自验</text>
          </g>

          <!-- Node 7: Guard -->
          <g id="node-guard" class="node-box" transform="translate(365, 340)">
            <rect width="190" height="38" rx="6" fill="url(#grad-guard)" stroke="#f59e0b" stroke-width="1.2"/>
            <text x="95" y="16" fill="#fbbf24" font-size="10.5" font-weight="700" text-anchor="middle">Policy 拦截 / 人工审批 (HITL)</text>
            <text x="95" y="30" fill="#fef08a" font-size="9.5" font-family="monospace" text-anchor="middle">幂等校验 · Append-only 审计</text>
          </g>

          <!-- Node 8: IncidentService (Core) -->
          <g id="node-core" class="node-box" transform="translate(630, 145)">
            <rect width="120" height="78" rx="10" fill="url(#grad-core)" stroke="#38bdf8" stroke-width="1.8"/>
            <text x="60" y="25" fill="#ffffff" font-size="12" font-weight="800" text-anchor="middle">IncidentService</text>
            <text x="60" y="40" fill="#bae6fd" font-size="10" font-weight="600" text-anchor="middle">唯一业务事实入口</text>
            <text x="60" y="56" fill="#7dd3fc" font-size="9" text-anchor="middle">五阶段状态机</text>
            <text x="60" y="69" fill="#38bdf8" font-size="8.5" font-family="monospace" text-anchor="middle">SQLite / PolarDB</text>
          </g>

          <!-- Node 9: 12 MCP Tools -->
          <g id="node-mcp" class="node-box" transform="translate(795, 150)">
            <rect width="105" height="70" rx="8" fill="#0f172a" stroke="#475569" stroke-width="1.5"/>
            <text x="52" y="24" fill="#38bdf8" font-size="11" font-weight="700" text-anchor="middle">12 个 P0 MCP</text>
            <text x="52" y="40" fill="#94a3b8" font-size="9.5" text-anchor="middle">设备 · 库存 · 停售</text>
            <text x="52" y="55" fill="#94a3b8" font-size="9.5" text-anchor="middle">审批 · 工单</text>
          </g>
        </svg>
      </div>
    </div>

    <!-- Live Narrative Bar -->
    <div id="narrative-bar" class="px-4 py-2.5 rounded-xl bg-slate-900/90 border border-slate-800 text-xs text-slate-300 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-sky-400 animate-ping"></span>
        <span id="narrative-text" class="text-slate-300">
          【全局就绪】系统正常监控中。点击「自动演练」查看冷柜失温飙升至 9.6°C、触发 Westgard 告警、Executor 停售锁、维修降温及 Auditor 独立重查阻断全流程。
        </span>
      </div>
      <span class="text-sky-400 font-mono text-[11px] whitespace-nowrap" id="timer-pill">00:00 / 01:00</span>
    </div>

  </div>

  <!-- Interactive JavaScript -->
  <script>
    const PHASES = [
      {
        phase: 1,
        time: "00-10s",
        name: "1. 巡检发现失温 (Sentry)",
        temp: "9.6°C",
        tempSub: "超出 8.0°C (Westgard +3SD)",
        devState: "CRITICAL (严重失温)",
        devColor: "#ef4444",
        goodsState: "RISK (超温暴露累积)",
        goodsColor: "#f59e0b",
        exposure: "15 min",
        cursorX: 380,
        cursorY: 42,
        exposureOpacity: 0.3,
        showHoldBadge: false,
        showRedlineBadge: false,
        activeNodes: ["node-input", "node-orch", "node-sentry", "node-core"],
        activePaths: ["path-input-orch", "path-orch-sentry", "path-sentry-core"],
        narrative: "【巡检发现】冷柜温度从 3.4°C 飙升至 9.6°C，触犯 Westgard 1-3s 规则。Sentry 校验数据排除传感器断流，标记 critical 严重度并向总控发出紧急遏制请求。"
      },
      {
        phase: 2,
        time: "10-20s",
        name: "2. Executor 紧急停售遏制",
        temp: "9.6°C",
        tempSub: "持续超温，POS 停售已锁定",
        devState: "CRITICAL (等待维修)",
        devColor: "#ef4444",
        goodsState: "HOLD_ACTIVE (已封存拦截)",
        goodsColor: "#f59e0b",
        exposure: "25 min",
        cursorX: 430,
        cursorY: 43,
        exposureOpacity: 0.5,
        showHoldBadge: true,
        showRedlineBadge: false,
        activeNodes: ["node-orch", "node-exec", "node-core", "node-mcp"],
        activePaths: ["path-orch-exec", "path-exec-core", "path-core-mcp", "path-mcp-core"],
        narrative: "【停售遏制】食品安全优先！Executor 立即执行 L1 预授权动作 apply_sales_hold，切断收银台结算，防止变质鲜奶与熟食流入顾客手中。"
      },
      {
        phase: 3,
        time: "20-30s",
        name: "3. Diagnoser 根因排查与暴露评估",
        temp: "9.4°C",
        tempSub: "门磁正常，压缩机未启动",
        devState: "DIAGNOSED (压缩机故障)",
        devColor: "#f59e0b",
        goodsState: "EXPOSURE_CRITICAL (变质预警)",
        goodsColor: "#ef4444",
        exposure: "35 min (>30m上限)",
        cursorX: 520,
        cursorY: 46,
        exposureOpacity: 0.7,
        showHoldBadge: true,
        showRedlineBadge: false,
        activeNodes: ["node-orch", "node-diag", "node-core"],
        activePaths: ["path-orch-diag", "path-diag-core"],
        narrative: "【根因诊断】Diagnoser 排查门磁与除霜，锁定压缩机电容老化（置信度 0.94）；计算鲜奶已超温暴露 35min，建议强制报损，熟食转移备用冷库。"
      },
      {
        phase: 4,
        time: "30-40s",
        name: "4. HITL 审批与换件降温",
        temp: "7.2°C",
        tempSub: "电容已更换，温度快速回落",
        devState: "REPAIRING (维保执行完成)",
        devColor: "#38bdf8",
        goodsState: "HOLD_ACTIVE (维持停售)",
        goodsColor: "#f59e0b",
        exposure: "42 min (暴露终止)",
        cursorX: 650,
        cursorY: 80,
        exposureOpacity: 0.8,
        showHoldBadge: true,
        showRedlineBadge: false,
        activeNodes: ["node-guard", "node-exec", "node-core", "node-mcp"],
        activePaths: ["path-guard-exec", "path-exec-core", "path-core-mcp", "path-mcp-core"],
        narrative: "【派修降温】维修费 ¥680 触发店长移动端审批核准。维保技工更换压缩机电容，冷柜重新制冷，温度快速从 9.6°C 回落至安全线以下！"
      },
      {
        phase: 5,
        time: "40-50s",
        name: "5. Auditor 独立稽核 (双重红线门禁)",
        temp: "4.8°C",
        tempSub: "已回落至 2~8°C 安全走廊",
        devState: "RECOVERED (设备完全恢复)",
        devColor: "#10b981",
        goodsState: "UNSAFE (鲜奶已变质·阻断放行!)",
        goodsColor: "#ef4444",
        exposure: "42 min (超标违规)",
        cursorX: 740,
        cursorY: 100,
        exposureOpacity: 0.9,
        showHoldBadge: true,
        showRedlineBadge: true,
        activeNodes: ["node-audit", "node-core", "node-mcp"],
        activePaths: ["path-audit-core", "path-audit-block"],
        narrative: "【核心红线高光时刻】设备温度虽已降至 4.8°C（设备恢复），但 Auditor 独立重查批次暴露达 42 分钟，判定鲜奶已变质，坚决阻断放行、强制报损！设备恢复 ≠ 商品安全！"
      },
      {
        phase: 6,
        time: "50-60s",
        name: "6. 复盘沉淀与安全关闭",
        temp: "4.5°C",
        tempSub: "温控持续平稳",
        devState: "NORMAL (闭环归档)",
        devColor: "#10b981",
        goodsState: "RESOLVED (变质销毁/熟食放行)",
        goodsColor: "#10b981",
        exposure: "归档记录完毕",
        cursorX: 820,
        cursorY: 102,
        exposureOpacity: 0.3,
        showHoldBadge: false,
        showRedlineBadge: false,
        activeNodes: ["node-orch", "node-audit", "node-core"],
        activePaths: ["path-orch-audit", "path-audit-core"],
        narrative: "【安全关闭】变质鲜奶销毁报损，熟食调拨合格放行，Auditor 生成复盘教训与启动电容老化知识条目，事件安全迁移为 CLOSED 终态。"
      }
    ];

    let currentPhase = 1;
    let isPlaying = false;
    let timerInterval = null;

    function resetHighlights() {
      document.querySelectorAll('#connections path').forEach(p => p.classList.remove('flow-line-active'));
      document.querySelectorAll('.node-box rect').forEach(r => r.classList.remove('node-active'));
      document.querySelectorAll('.phase-btn').forEach(b => {
        b.classList.remove('bg-sky-600', 'text-white');
        b.classList.add('text-slate-400');
      });
    }

    function setPhase(pNum) {
      resetHighlights();
      currentPhase = pNum;
      const data = PHASES[pNum - 1];

      // Highlight active button
      const tab = document.getElementById(`tab-p${pNum}`);
      if (tab) {
        tab.classList.add('bg-sky-600', 'text-white');
        tab.classList.remove('text-slate-400');
      }

      // Update Metric cards
      const tempEl = document.getElementById('gauge-temp');
      tempEl.textContent = data.temp;
      tempEl.style.color = data.devColor;
      document.getElementById('gauge-temp-sub').textContent = data.tempSub;

      const devStateEl = document.getElementById('gauge-dev-state');
      devStateEl.textContent = data.devState;
      devStateEl.style.color = data.devColor;

      const goodsStateEl = document.getElementById('gauge-goods-state');
      goodsStateEl.textContent = data.goodsState;
      goodsStateEl.style.color = data.goodsColor;

      document.getElementById('gauge-exposure').textContent = data.exposure;

      // Update Chart Cursor
      const cursor = document.getElementById('temp-cursor');
      cursor.setAttribute('transform', `translate(${data.cursorX}, ${data.cursorY})`);
      document.getElementById('cursor-label').textContent = data.temp;

      // Update Badges & Exposure Area
      document.getElementById('exposure-poly').setAttribute('opacity', data.exposureOpacity);
      document.getElementById('badge-containment').setAttribute('opacity', data.showHoldBadge ? '1' : '0');
      document.getElementById('badge-redline-block').setAttribute('opacity', data.showRedlineBadge ? '1' : '0');

      // Highlight Architecture Nodes
      data.activeNodes.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
          const rect = el.querySelector('rect');
          if (rect) rect.classList.add('node-active');
        }
      });

      // Highlight Architecture Paths
      data.activePaths.forEach(id => {
        const p = document.getElementById(id);
        if (p) p.classList.add('flow-line-active');
      });

      // Update Narratives
      document.getElementById('stage-name-text').textContent = data.name;
      document.getElementById('narrative-text').textContent = data.narrative;
      document.getElementById('timer-pill').textContent = `${data.time} · 阶段 ${pNum}/6`;
    }

    function togglePlay() {
      if (isPlaying) {
        clearInterval(timerInterval);
        isPlaying = false;
        document.getElementById('play-icon').textContent = '▶';
        document.getElementById('play-text').textContent = '继续演练';
      } else {
        isPlaying = true;
        document.getElementById('play-icon').textContent = '⏸';
        document.getElementById('play-text').textContent = '暂停演练';
        setPhase(currentPhase);
        timerInterval = setInterval(() => {
          currentPhase++;
          if (currentPhase > 6) currentPhase = 1;
          setPhase(currentPhase);
        }, 3500);
      }
    }

    function resetFlow() {
      clearInterval(timerInterval);
      isPlaying = false;
      document.getElementById('play-icon').textContent = '▶';
      document.getElementById('play-text').textContent = '自动演练 (60s)';
      setPhase(1);
    }

    // Initialize with Phase 1
    document.addEventListener('DOMContentLoaded', () => {
      setPhase(1);
    });
  </script>
</body>
</html>
"""

def build():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(HTML_CONTENT, encoding="utf-8")
    ARTIFACT_FILE.write_text(HTML_CONTENT, encoding="utf-8")
    print(f"Generated {OUTPUT_FILE} ({len(HTML_CONTENT)} bytes)")
    print(f"Updated artifact {ARTIFACT_FILE}")

if __name__ == "__main__":
    build()
