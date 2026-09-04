#!/usr/bin/env python3
"""Build Multi-Store, Multi-Device Fleet Temperature Monitoring + 5-Agent Architecture Animation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "dist" / "delivery-portal" / "architecture-flow.html"
ARTIFACT_FILE = Path("/Users/80371804/.gemini/antigravity/brain/b46ee03a-8a82-4354-b66d-7815347b840c/architecture_flow_animation.html")

HTML_CONTENT = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>店巡 Agent · 连锁多门店多设备实时巡检与多 Agent 闭环架构</title>
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
    @keyframes borderFlashRed {
      0%, 100% { border-color: rgba(239, 68, 68, 0.4); box-shadow: 0 0 10px rgba(239, 68, 68, 0.2); }
      50% { border-color: rgba(239, 68, 68, 0.9); box-shadow: 0 0 20px rgba(239, 68, 68, 0.5); }
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
    .device-critical-flash {
      animation: borderFlashRed 2s infinite;
    }
  </style>
</head>
<body class="bg-transparent text-[var(--foreground,#f1f5f9)] antialiased p-2 sm:p-4">
  <div class="bg-[var(--card,#0f172a)] border border-[var(--border,rgba(56,189,248,0.2))] rounded-2xl p-4 sm:p-5 shadow-2xl backdrop-blur-md max-w-5xl mx-auto space-y-4">
    
    <!-- Top Header & Global Controls -->
    <div class="flex flex-wrap justify-between items-center gap-3 pb-3 border-b border-[var(--border,rgba(255,255,255,0.1))]">
      <div>
        <div class="flex items-center gap-2">
          <span class="px-2 py-0.5 text-xs font-bold rounded bg-sky-500/20 text-sky-400 border border-sky-500/30">逐光队 · GOAI 赛道一</span>
          <h2 class="text-base sm:text-lg font-bold tracking-tight text-white flex items-center gap-2">
            店巡 Agent · 连锁多门店/多设备分布式巡检与 5-Agent 闭环
          </h2>
        </div>
        <p class="text-xs text-slate-400 mt-0.5">
          覆盖连锁多门店（S01~S04）与多温区设备集群（冷藏/冷冻/鲜食保温），Sentry 并行巡检与精准闭环
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

    <!-- ================= LEVEL 1: MULTI-STORE FLEET SELECTOR & KPIS ================= -->
    <div class="bg-slate-950/70 border border-slate-800 rounded-xl p-3 sm:p-4">
      <div class="flex flex-wrap justify-between items-center gap-3 mb-3">
        <div class="flex items-center gap-2">
          <span class="text-xs font-bold text-slate-300 flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-sky-400"></span>
            连锁门店网络 (128家门店 · 512台冷链设备在线)
          </span>
        </div>
        <!-- Fleet KPIs -->
        <div class="flex items-center gap-3 text-[11px] font-mono">
          <span class="text-slate-400">巡检周期: <b class="text-sky-400">30s/轮</b></span>
          <span class="text-slate-400">今日巡检: <b class="text-emerald-400">28,800次</b></span>
          <span class="text-slate-400">全网告警: <b class="text-red-400 animate-pulse">1 起异常闭环中</b></span>
        </div>
      </div>

      <!-- Store Tabs Selector -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3 text-xs">
        <!-- Store 1: S03 Active Incident -->
        <div class="bg-slate-900 border-2 border-red-500/80 rounded-lg p-2.5 cursor-pointer relative overflow-hidden transition-all shadow-lg shadow-red-950/30">
          <div class="flex justify-between items-start">
            <span class="font-bold text-white">S03 广州天河店</span>
            <span class="px-1.5 py-0.2 text-[9.5px] font-bold rounded bg-red-500/20 text-red-400 border border-red-500/40 animate-pulse">1 柜失温</span>
          </div>
          <div class="text-[10.5px] text-slate-400 mt-1">纳管设备: 4台 (1异常)</div>
          <div class="text-[10px] text-red-400 font-mono mt-0.5">Sentry 正在闭环处置中</div>
        </div>

        <!-- Store 2: S01 Normal -->
        <div class="bg-slate-900/60 border border-slate-800 hover:border-slate-700 rounded-lg p-2.5 cursor-pointer transition-all opacity-80 hover:opacity-100">
          <div class="flex justify-between items-start">
            <span class="font-bold text-slate-300">S01 深圳科技园店</span>
            <span class="px-1.5 py-0.2 text-[9.5px] font-bold rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">全绿正常</span>
          </div>
          <div class="text-[10.5px] text-slate-400 mt-1">纳管设备: 6台全部在线</div>
          <div class="text-[10px] text-emerald-400 font-mono mt-0.5">温度走廊 100% 达标</div>
        </div>

        <!-- Store 3: S02 Normal -->
        <div class="bg-slate-900/60 border border-slate-800 hover:border-slate-700 rounded-lg p-2.5 cursor-pointer transition-all opacity-80 hover:opacity-100">
          <div class="flex justify-between items-start">
            <span class="font-bold text-slate-300">S02 广州珠江新城店</span>
            <span class="px-1.5 py-0.2 text-[9.5px] font-bold rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">全绿正常</span>
          </div>
          <div class="text-[10.5px] text-slate-400 mt-1">纳管设备: 4台全部在线</div>
          <div class="text-[10px] text-emerald-400 font-mono mt-0.5">Westgard 质控合格</div>
        </div>

        <!-- Store 4: S04 Normal -->
        <div class="bg-slate-900/60 border border-slate-800 hover:border-slate-700 rounded-lg p-2.5 cursor-pointer transition-all opacity-80 hover:opacity-100">
          <div class="flex justify-between items-start">
            <span class="font-bold text-slate-300">S04 佛山千灯湖店</span>
            <span class="px-1.5 py-0.2 text-[9.5px] font-bold rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">全绿正常</span>
          </div>
          <div class="text-[10.5px] text-slate-400 mt-1">纳管设备: 5台全部在线</div>
          <div class="text-[10px] text-emerald-400 font-mono mt-0.5">无异常漂移事件</div>
        </div>
      </div>

      <!-- ================= LEVEL 2: S03 STORE MULTI-DEVICE FLEET CARDS ================= -->
      <div class="pt-2 border-t border-slate-800/80">
        <div class="flex justify-between items-center mb-2">
          <span class="text-xs font-semibold text-slate-300">当前聚焦门店：S03 广州天河店 · 设备集群监控矩阵（4 台不同温区冷链设备）</span>
          <span class="text-[11px] text-slate-500 font-mono">点击设备卡片可调阅对应独立时序与资产状态</span>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
          <!-- Device 1: FROST-S03-A (Abnormal Target) -->
          <div class="bg-slate-900 border-2 border-red-500/80 rounded-lg p-2.5 relative cursor-pointer device-critical-flash" id="card-dev-1">
            <div class="flex justify-between items-center text-[10.5px]">
              <span class="font-bold text-white">1号鲜奶冷藏立风柜</span>
              <span class="px-1 text-[9px] font-bold rounded bg-red-500 text-slate-950">失温闭环中</span>
            </div>
            <div class="flex items-baseline gap-1.5 my-1">
              <span class="text-xl font-black font-mono text-red-400" id="dev1-temp">9.6°C</span>
              <span class="text-[10px] text-slate-400 font-mono">阈值: 2~8°C</span>
            </div>
            <div class="text-[10px] text-slate-400">资产: 鲜牛奶 (超温暴露42m)</div>
            <div class="text-[10px] text-red-400 font-mono mt-0.5" id="dev1-status">Sentry 遏制 / Auditor 拦截</div>
          </div>

          <!-- Device 2: DEEP-S03-B (-18°C Freezer) -->
          <div class="bg-slate-900/60 border border-slate-800 rounded-lg p-2.5 opacity-85 hover:opacity-100 cursor-pointer transition-all">
            <div class="flex justify-between items-center text-[10.5px]">
              <span class="font-bold text-slate-300">2号冰淇淋冷冻岛柜</span>
              <span class="px-1 text-[9px] font-bold rounded bg-emerald-500/20 text-emerald-400">正常</span>
            </div>
            <div class="flex items-baseline gap-1.5 my-1">
              <span class="text-xl font-black font-mono text-emerald-400">-18.4°C</span>
              <span class="text-[10px] text-slate-400 font-mono">阈值: -22~-16°C</span>
            </div>
            <div class="text-[10px] text-slate-400">资产: 冷冻调制品 / 冰淇淋</div>
            <div class="text-[10px] text-emerald-400 font-mono mt-0.5">Sentry 巡检: 质控稳定</div>
          </div>

          <!-- Device 3: WARM-S03-C (60°C Hot Warmer) -->
          <div class="bg-slate-900/60 border border-slate-800 rounded-lg p-2.5 opacity-85 hover:opacity-100 cursor-pointer transition-all">
            <div class="flex justify-between items-center text-[10.5px]">
              <span class="font-bold text-slate-300">3号热食恒温包子柜</span>
              <span class="px-1 text-[9px] font-bold rounded bg-emerald-500/20 text-emerald-400">正常</span>
            </div>
            <div class="flex items-baseline gap-1.5 my-1">
              <span class="text-xl font-black font-mono text-amber-300">62.5°C</span>
              <span class="text-[10px] text-slate-400 font-mono">阈值: 60~68°C</span>
            </div>
            <div class="text-[10px] text-slate-400">资产: 鲜包 / 熟食保温</div>
            <div class="text-[10px] text-emerald-400 font-mono mt-0.5">Sentry 巡检: 恒温达标</div>
          </div>

          <!-- Device 4: COOL-S03-D (4°C Drink Cooler) -->
          <div class="bg-slate-900/60 border border-slate-800 rounded-lg p-2.5 opacity-85 hover:opacity-100 cursor-pointer transition-all">
            <div class="flex justify-between items-center text-[10.5px]">
              <span class="font-bold text-slate-300">4号低温饮料风幕柜</span>
              <span class="px-1 text-[9px] font-bold rounded bg-emerald-500/20 text-emerald-400">正常</span>
            </div>
            <div class="flex items-baseline gap-1.5 my-1">
              <span class="text-xl font-black font-mono text-emerald-400">3.8°C</span>
              <span class="text-[10px] text-slate-400 font-mono">阈值: 2~8°C</span>
            </div>
            <div class="text-[10px] text-slate-400">资产: 低温果汁 / 酸奶</div>
            <div class="text-[10px] text-emerald-400 font-mono mt-0.5">Sentry 巡检: 走廊居中</div>
          </div>
        </div>
      </div>

      <!-- ================= LEVEL 3: S03-1号冷柜动态实时折线与 WESTGARD 质控 ================= -->
      <div class="mt-3 pt-2 border-t border-slate-800/80">
        <div class="flex justify-between items-center mb-1 text-xs">
          <span class="font-medium text-slate-300 flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse"></span>
            当前分析焦点：S03 店 1号鲜奶冷柜时序走势与 Westgard 质控（Sentry 锁定）
          </span>
          <span class="text-[11px] font-mono text-slate-400">
            暴露积分: <b class="text-red-400" id="gauge-exposure">42 min</b> · 状态: <b class="text-red-400" id="gauge-goods-state">UNSAFE (鲜奶已变质)</b>
          </span>
        </div>

        <div class="relative w-full overflow-hidden bg-slate-900/80 rounded-lg border border-slate-800 p-2">
          <svg id="temp-svg" viewBox="0 0 900 170" class="w-full h-auto select-none font-mono">
            <defs>
              <linearGradient id="g-safe-band" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#10b981" stop-opacity="0.15"/>
                <stop offset="100%" stop-color="#10b981" stop-opacity="0.02"/>
              </linearGradient>
              <linearGradient id="g-danger-zone" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#ef4444" stop-opacity="0.35"/>
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

            <!-- Safe Corridor (2.0°C - 8.0°C) -->
            <rect x="70" y="50" width="810" height="65" fill="url(#g-safe-band)" rx="4"/>
            <line x1="70" y1="50" x2="880" y2="50" stroke="#f87171" stroke-width="1.2" stroke-dasharray="4,4"/>
            <text x="885" y="54" fill="#f87171" font-size="9.5" font-weight="700">8.0°C 告警上限</text>

            <line x1="70" y1="40" x2="880" y2="40" stroke="#fbbf24" stroke-width="1" stroke-dasharray="2,3"/>
            <text x="885" y="43" fill="#fbbf24" font-size="8.5">Westgard +3SD (8.5°C)</text>

            <line x1="70" y1="115" x2="880" y2="115" stroke="#34d399" stroke-width="1" stroke-dasharray="4,4"/>
            <text x="885" y="119" fill="#34d399" font-size="9.5">2.0°C 正常下限</text>

            <line x1="70" y1="92" x2="880" y2="92" stroke="#64748b" stroke-width="0.8" stroke-dasharray="2,4"/>
            <text x="885" y="95" fill="#64748b" font-size="8.5">均值 Mean (4.2°C)</text>

            <!-- Axes -->
            <line x1="70" y1="15" x2="70" y2="140" stroke="#334155" stroke-width="1"/>
            <line x1="70" y1="140" x2="880" y2="140" stroke="#334155" stroke-width="1"/>

            <!-- Y Axis Labels -->
            <text x="62" y="32" fill="#94a3b8" font-size="9.5" text-anchor="end">10.0°C</text>
            <text x="62" y="54" fill="#f87171" font-size="9.5" font-weight="700" text-anchor="end">8.0°C</text>
            <text x="62" y="95" fill="#94a3b8" font-size="9.5" text-anchor="end">4.0°C</text>
            <text x="62" y="119" fill="#34d399" font-size="9.5" text-anchor="end">2.0°C</text>

            <!-- X Axis Time Marks -->
            <text x="80" y="155" fill="#64748b" font-size="9.5">08:20</text>
            <text x="210" y="155" fill="#64748b" font-size="9.5">08:40</text>
            <text x="350" y="155" fill="#64748b" font-size="9.5">09:00 (Sentry超温)</text>
            <text x="490" y="155" fill="#64748b" font-size="9.5">09:15 (维修派单)</text>
            <text x="630" y="155" fill="#64748b" font-size="9.5">09:35 (换件降温)</text>
            <text x="780" y="155" fill="#64748b" font-size="9.5">09:50 (Auditor重查)</text>

            <!-- Exposure Fill Area -->
            <polygon id="exposure-poly" points="260,50 260,50 630,50 630,50" fill="url(#g-danger-zone)" opacity="0"/>

            <!-- Temperature Line -->
            <path id="temp-line" d="M 80 102 Q 160 100, 230 98 T 300 48 T 380 32 T 480 34 T 570 38 Q 620 42, 690 84 T 820 90" fill="none" stroke="url(#g-curve)" stroke-width="2.5"/>

            <!-- Cursor -->
            <g id="temp-cursor" transform="translate(80, 102)">
              <circle r="12" fill="#38bdf8" opacity="0.3" class="temp-pulse-beacon"/>
              <circle r="4.5" fill="#38bdf8" stroke="#ffffff" stroke-width="1.8"/>
              <rect x="-30" y="-24" width="60" height="18" rx="4" fill="#0f172a" stroke="#38bdf8" stroke-width="1"/>
              <text id="cursor-label" x="0" y="-12" fill="#38bdf8" font-size="9.5" font-weight="700" text-anchor="middle">3.4°C</text>
            </g>

            <!-- Badges -->
            <g id="badge-containment" transform="translate(340, 18)" opacity="0">
              <rect width="135" height="18" rx="4" fill="#78350f" stroke="#f59e0b" stroke-width="1"/>
              <text x="67" y="12" fill="#fef08a" font-size="9.5" font-weight="700" text-anchor="middle">🔒 Executor: 停售锁已下发</text>
            </g>

            <g id="badge-redline-block" transform="translate(660, 18)" opacity="0">
              <rect width="180" height="18" rx="4" fill="#450a0a" stroke="#ef4444" stroke-width="1.2"/>
              <text x="90" y="12" fill="#fca5a5" font-size="9.5" font-weight="700" text-anchor="middle">🛡️ Auditor: 鲜奶超温变质阻断放行!</text>
            </g>
          </svg>
        </div>
      </div>
    </div>

    <!-- ================= LEVEL 4: 5-AGENT ARCHITECTURE CLOSED-LOOP ================= -->
    <div class="bg-slate-950/70 border border-slate-800 rounded-xl p-3 sm:p-4">
      <div class="flex justify-between items-center mb-2">
        <div class="flex items-center gap-2">
          <span class="text-sky-400 font-bold text-xs">🤖 店巡 Agent · 全网调度与多 Agent 协同闭环中枢</span>
        </div>
        <div id="flow-status-text" class="text-xs text-slate-300 font-mono">
          当前协同状态：<span class="text-sky-400 font-bold" id="stage-name-text">Sentry 并行巡检全网</span>
        </div>
      </div>

      <!-- Architecture SVG Canvas -->
      <div class="relative w-full overflow-hidden bg-slate-900/40 rounded-lg border border-slate-800/80 p-1">
        <svg id="arch-svg" viewBox="0 0 940 370" class="w-full h-auto select-none">
          <defs>
            <linearGradient id="grad-orch" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#1e293b"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
            <linearGradient id="grad-core" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0369a1"/><stop offset="100%" stop-color="#0c4a6e"/></linearGradient>
            <linearGradient id="grad-guard" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#78350f"/><stop offset="100%" stop-color="#451a03"/></linearGradient>
            <linearGradient id="grad-worker" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#1e293b"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>

            <marker id="arr-cyan" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 1 L 9 5 L 0 9 z" fill="#38bdf8"/></marker>
            <marker id="arr-amber" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 1 L 9 5 L 0 9 z" fill="#f59e0b"/></marker>
            <marker id="arr-red" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 1 L 9 5 L 0 9 z" fill="#ef4444"/></marker>
          </defs>

          <!-- Paths -->
          <g id="connections">
            <path id="path-input-orch" d="M 120 180 L 180 180" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-orch-sentry" d="M 290 160 C 330 160, 340 55, 390 55" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-orch-diag" d="M 290 170 C 335 170, 340 130, 390 130" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-orch-exec" d="M 290 190 C 335 190, 340 210, 390 210" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-orch-audit" d="M 290 200 C 330 200, 340 290, 390 290" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>

            <path id="path-sentry-core" d="M 530 55 C 580 55, 590 160, 630 165" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-diag-core" d="M 530 130 C 575 130, 585 170, 630 175" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-exec-core" d="M 530 210 C 575 210, 585 185, 630 185" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-audit-core" d="M 530 290 C 580 290, 590 195, 630 195" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>

            <path id="path-core-mcp" d="M 750 175 L 795 175" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>
            <path id="path-mcp-core" d="M 795 195 L 750 195" fill="none" class="flow-line" marker-end="url(#arr-cyan)"/>

            <path id="path-guard-exec" d="M 460 340 L 460 245" fill="none" class="flow-line-guard" marker-end="url(#arr-amber)"/>
            <path id="path-audit-block" d="M 460 320 C 460 360, 690 360, 695 225" fill="none" class="flow-line-redline" marker-end="url(#arr-red)"/>
          </g>

          <!-- Redline Annotation Label -->
          <g transform="translate(530, 350)">
            <rect x="-10" y="-12" width="220" height="22" rx="5" fill="#450a0a" stroke="#ef4444" stroke-width="1"/>
            <text x="100" y="3" fill="#fca5a5" font-size="10.5" font-weight="700" text-anchor="middle">
              ⚠ 未通过则阻断关闭或回开 (核心红线)
            </text>
          </g>

          <!-- Nodes -->
          <g id="node-input" class="node-box" transform="translate(15, 145)">
            <rect width="105" height="70" rx="8" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>
            <text x="52" y="26" fill="#94a3b8" font-size="10" font-weight="600" text-anchor="middle">128家门店遥测</text>
            <text x="52" y="44" fill="#38bdf8" font-size="11.5" font-weight="700" text-anchor="middle">全网冷链数据</text>
            <text x="52" y="58" fill="#64748b" font-size="9" text-anchor="middle">512台时序矩阵</text>
          </g>

          <g id="node-orch" class="node-box" transform="translate(180, 140)">
            <rect width="110" height="80" rx="10" fill="url(#grad-orch)" stroke="#38bdf8" stroke-width="1.8"/>
            <rect x="20" y="-9" width="70" height="18" rx="4" fill="#0284c7"/>
            <text x="55" y="3" fill="#ffffff" font-size="9" font-weight="800" text-anchor="middle">TEAM LEADER</text>
            <text x="55" y="32" fill="#ffffff" font-size="13" font-weight="700" text-anchor="middle">Orchestrator</text>
            <text x="55" y="49" fill="#94a3b8" font-size="10" text-anchor="middle">全网分发与汇总</text>
            <text x="55" y="64" fill="#38bdf8" font-size="9.5" font-family="monospace" text-anchor="middle">qwen3.8-max</text>
          </g>

          <g id="node-sentry" class="node-box" transform="translate(390, 30)">
            <rect width="140" height="54" rx="8" fill="url(#grad-worker)" stroke="#475569" stroke-width="1.5"/>
            <text x="70" y="21" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">Sentry (全网守卫)</text>
            <text x="70" y="35" fill="#94a3b8" font-size="10" text-anchor="middle">512台并行巡检 · 去噪</text>
            <text x="70" y="47" fill="#10b981" font-size="9" font-family="monospace" text-anchor="middle">L0 只读 · 锁定异常单柜</text>
          </g>

          <g id="node-diag" class="node-box" transform="translate(390, 105)">
            <rect width="140" height="54" rx="8" fill="url(#grad-worker)" stroke="#475569" stroke-width="1.5"/>
            <text x="70" y="21" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">Diagnoser (根因诊断)</text>
            <text x="70" y="35" fill="#94a3b8" font-size="10" text-anchor="middle">柜门/除霜/压缩机排查</text>
            <text x="70" y="47" fill="#10b981" font-size="9" font-family="monospace" text-anchor="middle">L0 只读 · 批次暴露评估</text>
          </g>

          <g id="node-exec" class="node-box" transform="translate(390, 185)">
            <rect width="140" height="54" rx="8" fill="url(#grad-worker)" stroke="#f59e0b" stroke-width="1.5"/>
            <text x="70" y="21" fill="#fcd34d" font-size="12" font-weight="700" text-anchor="middle">Executor (受控执行)</text>
            <text x="70" y="35" fill="#94a3b8" font-size="10" text-anchor="middle">停售隔离 · 派单到店</text>
            <text x="70" y="47" fill="#f59e0b" font-size="9" font-family="monospace" text-anchor="middle">L1/L2 受控写 · 严格幂等</text>
          </g>

          <g id="node-audit" class="node-box" transform="translate(390, 265)">
            <rect width="140" height="54" rx="8" fill="url(#grad-worker)" stroke="#ef4444" stroke-width="1.8"/>
            <text x="70" y="21" fill="#fca5a5" font-size="12" font-weight="700" text-anchor="middle">Auditor (独立稽核)</text>
            <text x="70" y="35" fill="#cbd5e1" font-size="10" text-anchor="middle">独立重查事实 · 防自验</text>
            <text x="70" y="47" fill="#ef4444" font-size="9" font-family="monospace" text-anchor="middle">核心红线：阻断变质放行</text>
          </g>

          <g id="node-guard" class="node-box" transform="translate(365, 335)">
            <rect width="190" height="34" rx="6" fill="url(#grad-guard)" stroke="#f59e0b" stroke-width="1.2"/>
            <text x="95" y="15" fill="#fbbf24" font-size="10" font-weight="700" text-anchor="middle">Policy 拦截 / 店长移动端审批 (HITL)</text>
            <text x="95" y="27" fill="#fef08a" font-size="8.5" font-family="monospace" text-anchor="middle">幂等校验 · Append-only 审计</text>
          </g>

          <g id="node-core" class="node-box" transform="translate(630, 145)">
            <rect width="120" height="78" rx="10" fill="url(#grad-core)" stroke="#38bdf8" stroke-width="1.8"/>
            <text x="60" y="25" fill="#ffffff" font-size="12" font-weight="800" text-anchor="middle">IncidentService</text>
            <text x="60" y="40" fill="#bae6fd" font-size="10" font-weight="600" text-anchor="middle">唯一业务事实入口</text>
            <text x="60" y="56" fill="#7dd3fc" font-size="9" text-anchor="middle">全网五阶段状态机</text>
            <text x="60" y="69" fill="#38bdf8" font-size="8.5" font-family="monospace" text-anchor="middle">SQLite / PolarDB</text>
          </g>

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
          【全网巡检就绪】Sentry 持续轮询 128 家门店、512 台设备。S01/S02/S04 全部达标，精准锁定 S03 门店 1号鲜奶冷柜失温异常，自动触发闭环。
        </span>
      </div>
      <span class="text-sky-400 font-mono text-[11px] whitespace-nowrap" id="timer-pill">00:00 / 01:00</span>
    </div>

  </div>

  <!-- Interactive JavaScript Engine -->
  <script>
    const PHASES = [
      {
        phase: 1,
        time: "00-10s",
        name: "1. 全网巡检：锁定 S03 店 1号柜失温",
        temp: "9.6°C",
        dev1Status: "失温报警 (9.6°C)",
        exposure: "15 min",
        cursorX: 380,
        cursorY: 32,
        exposureOpacity: 0.3,
        showHoldBadge: false,
        showRedlineBadge: false,
        activeNodes: ["node-input", "node-orch", "node-sentry", "node-core"],
        activePaths: ["path-input-orch", "path-orch-sentry", "path-sentry-core"],
        narrative: "【全网去噪与失温发现】Sentry 并行轮询 128 店 512 台设备，排除瞬时开门波动，精准锁定 S03 店 1号鲜奶柜突破 Westgard +3SD (9.6°C)，发起紧急遏制！"
      },
      {
        phase: 2,
        time: "10-20s",
        name: "2. S03 店 Executor 紧急停售遏制",
        temp: "9.6°C",
        dev1Status: "POS停售锁定中",
        exposure: "25 min",
        cursorX: 430,
        cursorY: 34,
        exposureOpacity: 0.5,
        showHoldBadge: true,
        showRedlineBadge: false,
        activeNodes: ["node-orch", "node-exec", "node-core", "node-mcp"],
        activePaths: ["path-orch-exec", "path-exec-core", "path-core-mcp", "path-mcp-core"],
        narrative: "【单店单柜停售】Executor 联动 S03 店 POS 系统下发商品停售锁，切断该柜鲜奶与熟食结算，同时其他 511 台正常设备丝毫不受影响！"
      },
      {
        phase: 3,
        time: "20-30s",
        name: "3. Diagnoser 根因排查与暴露计算",
        temp: "9.4°C",
        dev1Status: "诊断锁定: 压缩机电容",
        exposure: "35 min (>30m上限)",
        cursorX: 520,
        cursorY: 36,
        exposureOpacity: 0.7,
        showHoldBadge: true,
        showRedlineBadge: false,
        activeNodes: ["node-orch", "node-diag", "node-core"],
        activePaths: ["path-orch-diag", "path-diag-core"],
        narrative: "【多源诊断】Diagnoser 综合排查门磁与除霜，锁定 1 号柜压缩机电容老化（0.94置信度）；计算鲜奶超温暴露达 35min，建议强制报损，熟食调拨备用冷柜。"
      },
      {
        phase: 4,
        time: "30-40s",
        name: "4. S03 店长移动端审批与到店急修",
        temp: "7.2°C",
        dev1Status: "技工已换件·降温中",
        exposure: "42 min (暴露终止)",
        cursorX: 650,
        cursorY: 70,
        exposureOpacity: 0.8,
        showHoldBadge: true,
        showRedlineBadge: false,
        activeNodes: ["node-guard", "node-exec", "node-core", "node-mcp"],
        activePaths: ["path-guard-exec", "path-exec-core", "path-core-mcp", "path-mcp-core"],
        narrative: "【HITL 审批与派修】维修预算超限自动推送 S03 店长手机审批核准。冷修维保人员到店更换电容，冷柜重新轰鸣制冷，温度快速回落至安全线！"
      },
      {
        phase: 5,
        time: "40-50s",
        name: "5. Auditor 独立稽核 (核心红线阻断放行)",
        temp: "4.8°C",
        dev1Status: "设备修好 · 鲜奶阻断!",
        exposure: "42 min (超标违规)",
        cursorX: 740,
        cursorY: 88,
        exposureOpacity: 0.9,
        showHoldBadge: true,
        showRedlineBadge: true,
        activeNodes: ["node-audit", "node-core", "node-mcp"],
        activePaths: ["path-audit-core", "path-audit-block"],
        narrative: "【核心红线高光时刻】1 号柜温度虽已恢复至 4.8°C（设备完全恢复），但 Auditor 独立重查批次暴露达 42 分钟，判定鲜奶已变质，坚决阻断放行、强制报损！设备恢复 ≠ 商品安全！"
      },
      {
        phase: 6,
        time: "50-60s",
        name: "6. 复盘知识沉淀与全网安全复归",
        temp: "4.5°C",
        dev1Status: "闭环完成 · 恢复绿灯",
        exposure: "已归档记录",
        cursorX: 820,
        cursorY: 90,
        exposureOpacity: 0.2,
        showHoldBadge: false,
        showRedlineBadge: false,
        activeNodes: ["node-orch", "node-audit", "node-core"],
        activePaths: ["path-orch-audit", "path-audit-core"],
        narrative: "【闭环关闭】变质鲜奶销毁，熟食转库复验合格放行。Auditor 生成启动电容老化知识条目并入库待审，S03 店 1 号柜复归正常，全网 512 台设备重归全绿守护！"
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

      // Update Device 1 Card
      document.getElementById('dev1-temp').textContent = data.temp;
      document.getElementById('dev1-status').textContent = data.dev1Status;
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
