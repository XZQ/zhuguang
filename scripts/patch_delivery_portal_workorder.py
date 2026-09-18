#!/usr/bin/env python3
"""Inject Work Order & Risk-Control Playground into delivery_portal_html_content.html."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "scripts" / "assets" / "delivery_portal_html_content.html"

WO_CSS = """
/* ==================== WORK ORDER & RISK CONTROL PLAYGROUND STYLES ==================== */
.wo-container {
  margin-bottom: 30px;
}
.wo-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.wo-form-group {
  margin-bottom: 14px;
}
.wo-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.wo-input, .wo-select, .wo-textarea {
  width: 100%;
  box-sizing: border-box;
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: #fff;
  font-family: var(--font-sans);
  transition: border-color 0.2s;
}
.wo-input:focus, .wo-select:focus, .wo-textarea:focus {
  outline: none;
  border-color: var(--cyan);
  box-shadow: 0 0 8px rgba(56, 189, 248, 0.25);
}
.wo-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-mono);
}
.wo-badge.green { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
.wo-badge.amber { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
.wo-badge.red { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
.wo-badge.cyan { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
.wo-badge.purple { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }

/* Lifecycle Stepper */
.wo-steps {
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  margin: 18px 0 22px 0;
  padding: 0 10px;
}
.wo-steps::before {
  content: '';
  position: absolute;
  top: 14px;
  left: 20px;
  right: 20px;
  height: 2px;
  background: var(--border);
  z-index: 1;
}
.wo-step {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  text-align: center;
}
.wo-step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #0f172a;
  border: 2px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  transition: all 0.3s;
}
.wo-step.active .wo-step-dot {
  background: rgba(56, 189, 248, 0.2);
  border-color: var(--cyan);
  color: #fff;
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.5);
}
.wo-step.completed .wo-step-dot {
  background: rgba(16, 185, 129, 0.2);
  border-color: var(--green);
  color: var(--green);
}
.wo-step.vetoed .wo-step-dot {
  background: rgba(239, 68, 68, 0.2);
  border-color: var(--red);
  color: var(--red);
}
.wo-step-label {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.wo-step.active .wo-step-label {
  color: var(--cyan);
  font-weight: 700;
}
.wo-step.completed .wo-step-label {
  color: var(--green);
}
.wo-step.vetoed .wo-step-label {
  color: var(--red);
  font-weight: 700;
}

/* Console Logs */
.wo-console {
  background: #030712;
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  padding: 12px 16px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: #94a3b8;
  height: 190px;
  overflow-y: auto;
  line-height: 1.6;
}
.wo-console .log-line {
  margin-bottom: 4px;
  word-break: break-all;
}
.wo-console .log-time { color: #64748b; margin-right: 6px; }
.wo-console .log-green { color: #34d399; }
.wo-console .log-cyan { color: #38bdf8; }
.wo-console .log-amber { color: #fbbf24; }
.wo-console .log-red { color: #f87171; }
.wo-console .log-purple { color: #c084fc; }
"""

WO_SECTION = """
  <!-- ==================== SECTION: REAL WORK ORDER & RISK CONTROL PLAYGROUND ==================== -->
  <section id="view-workorder" class="view-section active">
    <!-- Header Summary Card -->
    <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(16, 36, 64, 0.95)); border: 1.5px solid rgba(56, 189, 248, 0.35); border-radius: 16px; padding: 24px; box-shadow: 0 10px 35px rgba(0,0,0,0.5); margin-bottom: 24px;">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px; margin-bottom:18px;">
        <div>
          <h2 style="font-size: 21px; color:#fff; margin:0; display:flex; align-items:center; gap:10px;">
            <span>📋 VeriAgent 工单全生命周期与风控演练控制台</span>
            <span style="font-size:11px; background:rgba(16,185,129,0.2); color:#34d399; border:1px solid rgba(16,185,129,0.4); padding:3px 10px; border-radius:6px; font-weight:700;">
              真实 SQLite 数据库落盘 · 刚性风控门禁实测
            </span>
          </h2>
          <p style="color:var(--text-secondary); font-size:13px; margin:8px 0 0 0; line-height:1.5;">
            解决传统多 Agent 运维“伪闭环/虚报完成”隐患：提供清晰的<b>端到端正常标准工单流程 (Happy Path)</b>，并配备<b>4大极端风控状况一键启动台</b>。每一次操作均由策略引擎（Policy Engine）刚性约束，并由带外独立审计员（Auditor）双门物理验真。
          </p>
        </div>
        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
          <button class="header-btn" onclick="fetchLiveStatus()" style="background:rgba(56,189,248,0.15); border-color:var(--cyan); color:#38bdf8;">
            🔄 刷新云端数据库状态
          </button>
          <button class="header-btn" onclick="resetLiveDatabase()" style="background:rgba(239,68,68,0.12); border-color:rgba(239,68,68,0.4); color:#fca5a5;">
            🧹 清空测试工单数据
          </button>
        </div>
      </div>

      <!-- Live Database Health & Counts Bar -->
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:12px; background:rgba(0,0,0,0.35); border:1px solid var(--border-subtle); border-radius:12px; padding:14px 18px;">
        <div>
          <div style="font-size:11px; color:var(--text-muted); display:flex; align-items:center; gap:6px;">
            <span class="pulse-dot"></span> 云端后端 SQLite
          </div>
          <div id="wo-db-indicator" style="font-size:13px; font-weight:700; color:var(--green); margin-top:2px; font-family:var(--font-mono);">
            runtime.db 在线读写
          </div>
        </div>
        <div>
          <div style="font-size:11px; color:var(--text-muted);">📋 工单记录 (workorders)</div>
          <div id="wo-live-count" style="font-size:18px; font-weight:800; color:var(--cyan); font-family:var(--font-mono);">
            0 条落盘
          </div>
        </div>
        <div>
          <div style="font-size:11px; color:var(--text-muted);">🔒 审批记录 (approvals)</div>
          <div id="app-live-count" style="font-size:18px; font-weight:800; color:var(--amber); font-family:var(--font-mono);">
            0 条挂起/已决
          </div>
        </div>
        <div>
          <div style="font-size:11px; color:var(--text-muted);">🧊 纳管设备 (devices)</div>
          <div id="dev-live-count" style="font-size:13px; font-weight:700; color:#fff; font-family:var(--font-mono); margin-top:3px;">
            FROST-S03 (故障停转)
          </div>
        </div>
        <div>
          <div style="font-size:11px; color:var(--text-muted);">🛡️ 防篡改审计 (audit_log)</div>
          <div id="audit-live-count" style="font-size:18px; font-weight:800; color:#a78bfa; font-family:var(--font-mono);">
            0 笔存证
          </div>
        </div>
      </div>
    </div>

    <!-- 4 Risk-Control Condition Launchers -->
    <div style="margin-bottom: 24px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
        <h3 style="font-size:15px; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
          <span>⚡ 核心状况一键启动控制台 (点击启动各种状况 · 验证系统风控真实性)</span>
        </h3>
        <span style="font-size:12px; color:var(--text-muted);">💡 点击卡片直接载入对应业务参数，实测风控拦截与闭环表现</span>
      </div>

      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:14px;">
        <!-- Scenario 0: Happy Path -->
        <div id="sc-card-happy" class="scenario-card" onclick="loadScenario('happy_path')" style="background:rgba(16,185,129,0.06); border:1.5px solid rgba(16,185,129,0.4); border-radius:12px; padding:16px; cursor:pointer; transition:all 0.2s;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:12px; font-weight:700; background:rgba(16,185,129,0.2); color:#34d399; padding:2px 8px; border-radius:4px;">正常标准流程 (Happy Path)</span>
            <span style="font-size:11px; color:var(--green); font-weight:700;">免批下发</span>
          </div>
          <div style="font-size:14px; font-weight:700; color:#fff; margin-bottom:6px;">日常电容失效更换 (¥420)</div>
          <p style="font-size:12px; color:var(--text-secondary); line-height:1.4; margin-bottom:12px;">
            预算 ¥420 ≤ 门禁限额 ¥500。Sentry 告警 ➔ Executor 免审直接派单 ➔ 施工降温至 4.2°C ➔ Auditor 双门独立验真闭环。
          </p>
          <button class="header-btn" style="width:100%; justify-content:center; background:rgba(16,185,129,0.2); border-color:var(--green); color:#fff; font-weight:700;">
            ▶️ 启动正常流程演练
          </button>
        </div>

        <!-- Scenario 1: HITL Gate -->
        <div id="sc-card-hitl" class="scenario-card" onclick="loadScenario('hitl_gate')" style="background:rgba(239,68,68,0.06); border:1.5px solid rgba(239,68,68,0.4); border-radius:12px; padding:16px; cursor:pointer; transition:all 0.2s;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:12px; font-weight:700; background:rgba(239,68,68,0.2); color:#fca5a5; padding:2px 8px; border-radius:4px;">状况一：高额预算刚性门禁</span>
            <span style="font-size:11px; color:#f87171; font-weight:700;">HITL 拦截</span>
          </div>
          <div style="font-size:14px; font-weight:700; color:#fff; margin-bottom:6px;">核心大修换压缩机 (¥850)</div>
          <p style="font-size:12px; color:var(--text-secondary); line-height:1.4; margin-bottom:12px;">
            预算 ¥850 > 权限门禁 ¥500！系统刚性拦截下发并挂起，用户可实测<b>【店长拒绝】(0写入/Auditor打回)</b>与<b>【店长批准】(放行落库)</b>。
          </p>
          <button class="header-btn" style="width:100%; justify-content:center; background:rgba(239,68,68,0.2); border-color:var(--red); color:#fff; font-weight:700;">
            ⚠️ 启动超额风控状况
          </button>
        </div>

        <!-- Scenario 2: Anti-Self-Verification -->
        <div id="sc-card-asv" class="scenario-card" onclick="loadScenario('anti_self_verify')" style="background:rgba(245,158,11,0.06); border:1.5px solid rgba(245,158,11,0.4); border-radius:12px; padding:16px; cursor:pointer; transition:all 0.2s;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:12px; font-weight:700; background:rgba(245,158,11,0.2); color:#fde68a; padding:2px 8px; border-radius:4px;">状况二：物理反自验一票否决</span>
            <span style="font-size:11px; color:#fbbf24; font-weight:700;">不可逆变质</span>
          </div>
          <div style="font-size:14px; font-weight:700; color:#fff; margin-bottom:6px;">冷柜修好但鲜奶酸败 (48m暴露)</div>
          <p style="font-size:12px; color:var(--text-secondary); line-height:1.4; margin-bottom:12px;">
            师傅报修完工(4.5°C)，但 Auditor 积分核算鲜奶暴露48分钟已变质，<b>一票否决单方完工</b>，严禁解封POS，强制报损处置！
          </p>
          <button class="header-btn" style="width:100%; justify-content:center; background:rgba(245,158,11,0.2); border-color:var(--amber); color:#fff; font-weight:700;">
            🚨 启动物理反自验状况
          </button>
        </div>

        <!-- Scenario 3: RBAC Gate -->
        <div id="sc-card-rbac" class="scenario-card" onclick="loadScenario('rbac_unauthorized')" style="background:rgba(168,85,247,0.06); border:1.5px solid rgba(168,85,247,0.4); border-radius:12px; padding:16px; cursor:pointer; transition:all 0.2s;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:12px; font-weight:700; background:rgba(168,85,247,0.2); color:#ddd6fe; padding:2px 8px; border-radius:4px;">状况三：RBAC 越权调用熔断</span>
            <span style="font-size:11px; color:#c084fc; font-weight:700;">403 阻断</span>
          </div>
          <div style="font-size:14px; font-weight:700; color:#fff; margin-bottom:6px;">非授权 Agent 越权写库</div>
          <p style="font-size:12px; color:var(--text-secondary); line-height:1.4; margin-bottom:12px;">
            只读角色 Sentry 尝试越权调用 create_workorder 写库。网关校验 Token/Actor 抛出 403 熔断，底层数据库 0 穿透并记入审计。
          </p>
          <button class="header-btn" style="width:100%; justify-content:center; background:rgba(168,85,247,0.2); border-color:var(--purple); color:#fff; font-weight:700;">
            🛡️ 启动越权阻断状况
          </button>
        </div>
      </div>
    </div>

    <!-- Main Operational Split Console -->
    <div style="display:grid; grid-template-columns: 1fr 1.25fr; gap:20px; margin-bottom:24px;">
      
      <!-- LEFT: Work Order Submission & Parameters Form -->
      <div class="wo-card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; border-bottom:1px solid var(--border-subtle); padding-bottom:12px;">
          <h3 style="font-size:16px; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
            <span>📝 工单调度与派发表单</span>
          </h3>
          <span id="wo-actor-badge" class="wo-badge green">角色: Executor (执行器)</span>
        </div>

        <form id="wo-form" onsubmit="event.preventDefault(); submitWorkOrder();">
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
            <div class="wo-form-group">
              <label class="wo-label">目标门店 (Store)</label>
              <select id="wo-store-id" class="wo-select">
                <option value="S03">S03 · 广州天河生鲜店</option>
                <option value="S07">S07 · 广州番禺便利店</option>
              </select>
            </div>
            <div class="wo-form-group">
              <label class="wo-label">目标设备 (Device)</label>
              <select id="wo-device-id" class="wo-select">
                <option value="FROST-S03">FROST-S03 (风冷多门立式柜 · 故障中)</option>
                <option value="FROST-S07">FROST-S07 (风冷卧式冷柜 · 正常)</option>
              </select>
            </div>
          </div>

          <div class="wo-form-group">
            <label class="wo-label">故障现象与诊断结论 (Fault)</label>
            <input type="text" id="wo-fault" class="wo-input" value="压缩机启动电容老化失效 / 停转故障" required>
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
            <div class="wo-form-group">
              <label class="wo-label">
                维修预算金额 (Budget ¥)
                <span id="wo-budget-hint" style="color:#34d399; font-size:11px; margin-left:4px;">(≤ ¥500 免审)</span>
              </label>
              <input type="number" id="wo-budget" class="wo-input" value="420" min="0" step="10" required oninput="handleBudgetInput(this.value)">
            </div>
            <div class="wo-form-group">
              <label class="wo-label">维保服务商 (Assignee)</label>
              <select id="wo-assignee" class="wo-select">
                <option value="冷链特约维保中心 (Vendor A)">冷链特约维保中心 (Vendor A)</option>
                <option value="应急抢修工程队 (Vendor B)">应急抢修工程队 (Vendor B)</option>
              </select>
            </div>
          </div>

          <div style="display:grid; grid-template-columns:1.2fr 1fr; gap:12px;">
            <div class="wo-form-group">
              <label class="wo-label">幂等防重 Key (Idempotency Key)</label>
              <div style="display:flex; gap:6px;">
                <input type="text" id="wo-idemp-key" class="wo-input" style="font-family:var(--font-mono); font-size:11px;" value="IDEMP-WO-20260918-001" readonly>
                <button type="button" class="header-btn" onclick="regenerateIdempKey()" title="重新生成" style="padding:6px 10px;">🎲</button>
              </div>
            </div>
            <div class="wo-form-group">
              <label class="wo-label">调用角色身份 (Actor)</label>
              <select id="wo-actor-select" class="wo-select" onchange="handleActorChange(this.value)">
                <option value="Executor">Executor (合法运维执行角色)</option>
                <option value="Sentry">Sentry (只读监测 · 越权测试)</option>
              </select>
            </div>
          </div>

          <div id="wo-threshold-warning" style="display:none; background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.4); border-radius:8px; padding:10px 14px; margin-bottom:14px; font-size:12px; color:#fca5a5;">
            ⚠️ <b>超额风控门禁提示</b>：当前预算超出日常授权限额 (¥500.00)！提交时将被策略引擎<b>刚性拦截并挂起</b>，必须经由店长数字签名授权方可落库！
          </div>

          <div style="display:flex; gap:10px; margin-top:8px;">
            <button type="submit" id="btn-submit-wo" class="header-btn primary" style="flex:1; justify-content:center; background:linear-gradient(135deg, #059669, #0284c7); border-color:#34d399; padding:10px 16px; font-size:13.5px;">
              🚀 真实提交到底层数据库 (Commit to SQLite)
            </button>
          </div>
        </form>
      </div>

      <!-- RIGHT: Work Order Lifecycle & Multi-Agent Action State Machine -->
      <div class="wo-card" style="display:flex; flex-direction:column; justify-content:space-between;">
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom:1px solid var(--border-subtle); padding-bottom:12px;">
            <h3 style="font-size:16px; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
              <span>🔄 工单生命周期与多 Agent 协同追踪</span>
            </h3>
            <span id="wo-status-badge" class="wo-badge cyan">待派发 (IDLE)</span>
          </div>

          <!-- 6-Stage Visual Stepper -->
          <div class="wo-steps">
            <div id="step-node-1" class="wo-step active">
              <div class="wo-step-dot">1</div>
              <div class="wo-step-label">Sentry 告警</div>
            </div>
            <div id="step-node-2" class="wo-step">
              <div class="wo-step-dot">2</div>
              <div class="wo-step-label">策略核准</div>
            </div>
            <div id="step-node-3" class="wo-step">
              <div class="wo-step-dot">3</div>
              <div class="wo-step-label">工单下发</div>
            </div>
            <div id="step-node-4" class="wo-step">
              <div class="wo-step-dot">4</div>
              <div class="wo-step-label">到场施工</div>
            </div>
            <div id="step-node-5" class="wo-step">
              <div class="wo-step-dot">5</div>
              <div class="wo-step-label">独立验真</div>
            </div>
            <div id="step-node-6" class="wo-step">
              <div class="wo-step-dot">6</div>
              <div class="wo-step-label">闭环解封</div>
            </div>
          </div>

          <!-- Work Order Live Receipt Box -->
          <div id="wo-receipt-box" style="background:rgba(0,0,0,0.4); border:1px solid var(--border-subtle); border-radius:12px; padding:16px; margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
              <div>
                <span style="font-size:11px; color:var(--text-muted);">工单流水号</span>
                <div id="wo-display-id" style="font-size:15px; font-weight:800; color:#fff; font-family:var(--font-mono);">
                  #WO-STANDBY (尚未下发)
                </div>
              </div>
              <div style="text-align:right;">
                <span style="font-size:11px; color:var(--text-muted);">SLA 应急倒计时</span>
                <div id="wo-sla-timer" style="font-size:14px; font-weight:700; color:var(--cyan); font-family:var(--font-mono);">
                  04:00:00
                </div>
              </div>
            </div>

            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:12px; border-top:1px solid rgba(255,255,255,0.06); padding-top:10px;">
              <div>所属门店：<span id="wo-disp-store" style="color:#fff;">S03 (广州天河店)</span></div>
              <div>关联设备：<span id="wo-disp-device" style="color:#fff;">FROST-S03</span></div>
              <div>故障性质：<span id="wo-disp-fault" style="color:#fff;">压缩机电容失效</span></div>
              <div>核准预算：<span id="wo-disp-budget" style="color:var(--green); font-weight:700;">¥420.00</span></div>
              <div>承修服务商：<span id="wo-disp-assignee" style="color:#fff;">冷链特约维保中心</span></div>
              <div>POS 状态：<span id="wo-disp-pos" style="color:var(--red); font-weight:700;">销售加锁停售中</span></div>
            </div>

            <!-- HITL Store Manager Decision Panel (Hidden by default) -->
            <div id="wo-hitl-panel" style="display:none; margin-top:14px; background:rgba(239,68,68,0.12); border:1.5px solid rgba(239,68,68,0.5); border-radius:10px; padding:14px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <b style="color:#fca5a5; font-size:13px; display:flex; align-items:center; gap:6px;">
                  🔒 店长刚性审批中心 (Human-in-the-Loop)
                </b>
                <span id="wo-hitl-appid" class="wo-badge red" style="font-size:10px;">APP-PENDING</span>
              </div>
              <p style="font-size:12px; color:#fee2e2; margin:0 0 10px 0; line-height:1.4;">
                维修预算 <b>¥850.00</b> 超出门店日常自主维修门禁 (¥500.00)。请店长在线签署审批决策：
              </p>
              <div style="display:flex; gap:10px;">
                <button type="button" class="header-btn" onclick="decideApproval('rejected')" style="flex:1; justify-content:center; background:rgba(239,68,68,0.25); border-color:var(--red); color:#fff; font-weight:700;">
                  ❌ 驳回 / 模拟审批超时 (0写入阻断)
                </button>
                <button type="button" class="header-btn primary" onclick="decideApproval('approved')" style="flex:1; justify-content:center; background:linear-gradient(135deg, #059669, #10b981); border-color:#34d399; color:#fff; font-weight:700;">
                  ✅ 授权同意大额支出 (合规落库)
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Dynamic Action Toolbar for Worker & Auditor -->
        <div style="border-top:1px solid var(--border-subtle); padding-top:14px;">
          <div style="font-size:12px; font-weight:600; color:var(--text-secondary); margin-bottom:8px;">
            业务闭环联动指令 (按流程阶段逐步激活)：
          </div>
          <div style="display:flex; gap:10px; flex-wrap:wrap;">
            <button id="btn-tech-arrive" class="header-btn" onclick="progressWorkOrder('in_progress')" disabled style="flex:1; justify-content:center;">
              👨‍🔧 师傅打卡开工 (IN_PROGRESS)
            </button>
            <button id="btn-tech-finish" class="header-btn" onclick="progressWorkOrder('pending_verification')" disabled style="flex:1; justify-content:center;">
              ✅ 施工完工报竣 (PENDING_VERIFY)
            </button>
            <button id="btn-auditor-verify" class="header-btn primary" onclick="verifyWorkOrder()" disabled style="flex:1.2; justify-content:center; background:linear-gradient(135deg, #4f46e5, #0284c7);">
              🛡️ Auditor 双门带外独立验真
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Real Data Inspector & Audit Trail -->
    <div class="wo-card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:10px;">
        <div style="display:flex; gap:12px; align-items:center;">
          <button id="btn-tab-dbrecords" class="header-btn primary" onclick="switchWoDataTab('records')" style="padding:6px 12px; font-size:12px;">
            📊 底层 SQLite 真实落盘表 (runtime.db)
          </button>
          <button id="btn-tab-auditlog" class="header-btn" onclick="switchWoDataTab('audit')" style="padding:6px 12px; font-size:12px;">
            🛡️ 防篡改不可逆审计链 (Audit Trail)
          </button>
          <button id="btn-tab-console" class="header-btn" onclick="switchWoDataTab('console')" style="padding:6px 12px; font-size:12px;">
            🖥️ 实时日志输出流 (Live Console)
          </button>
        </div>
        <span style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">
          存储路径: /home/ubuntu/agentteams-competition/runtime/mcp-state/runtime.db
        </span>
      </div>

      <!-- Tab View 1: Raw SQLite Records Table -->
      <div id="wo-tab-records" style="display:block;">
        <div style="overflow-x:auto;">
          <table style="width:100%; border-collapse:collapse; font-size:12px; font-family:var(--font-mono); text-align:left;">
            <thead>
              <tr style="border-bottom:1px solid var(--border); color:var(--text-secondary);">
                <th style="padding:8px 12px;">工单编号 (workorder_id)</th>
                <th style="padding:8px 12px;">关联事件 (incident_id)</th>
                <th style="padding:8px 12px;">设备 (device_id)</th>
                <th style="padding:8px 12px;">故障描述 (fault)</th>
                <th style="padding:8px 12px;">预算 (budget)</th>
                <th style="padding:8px 12px;">当前状态 (status)</th>
                <th style="padding:8px 12px;">创建时间 (created_at)</th>
              </tr>
            </thead>
            <tbody id="wo-tbody-records">
              <tr>
                <td colspan="7" style="padding:16px; text-align:center; color:var(--text-muted);">
                  底层 SQLite 数据库 workorders 表中暂无记录。请在上方表单提交或点击【正常标准流程】进行一键下发！
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tab View 2: Audit Logs -->
      <div id="wo-tab-audit" style="display:none;">
        <div style="overflow-x:auto;">
          <table style="width:100%; border-collapse:collapse; font-size:12px; font-family:var(--font-mono); text-align:left;">
            <thead>
              <tr style="border-bottom:1px solid var(--border); color:var(--text-secondary);">
                <th style="padding:8px 12px;">审计单号 (audit_id)</th>
                <th style="padding:8px 12px;">请求单号 (request_id)</th>
                <th style="padding:8px 12px;">操作角色 (actor)</th>
                <th style="padding:8px 12px;">调用工具 (tool_name)</th>
                <th style="padding:8px 12px;">准据策略 (policy_id)</th>
                <th style="padding:8px 12px;">存证时间 (created_at)</th>
              </tr>
            </thead>
            <tbody id="wo-tbody-audit">
              <tr>
                <td colspan="6" style="padding:16px; text-align:center; color:var(--text-muted);">
                  暂无审计存证记录。
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tab View 3: Live Terminal Console -->
      <div id="wo-tab-console" style="display:none;">
        <div class="wo-console" id="wo-console-output">
          <div class="log-line"><span class="log-time">[00:00:00]</span> <span class="log-cyan">[System]</span> VeriAgent 工单系统演练台初始化完成，等待操作指令...</div>
        </div>
      </div>
    </div>
  </section>
"""

WO_JS = """
// ==================== WORK ORDER & RISK CONTROL PLAYGROUND JS ====================
let currentWoRecord = null;
let currentApprovalId = null;
let currentScenarioMode = 'happy_path';
let liveDbStatus = null;

function appendWoLog(tag, msg, color = 'cyan') {
  const consoleEl = document.getElementById('wo-console-output');
  if (!consoleEl) return;
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0] + '.' + String(now.getMilliseconds()).padStart(3, '0');
  const line = document.createElement('div');
  line.className = 'log-line';
  line.innerHTML = `<span class="log-time">[${timeStr}]</span> <span class="log-${color}">[${tag}]</span> ${msg}`;
  consoleEl.appendChild(line);
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

function handleBudgetInput(val) {
  const budget = parseFloat(val) || 0;
  const hintEl = document.getElementById('wo-budget-hint');
  const warnEl = document.getElementById('wo-threshold-warning');
  if (budget > 500) {
    hintEl.innerHTML = '<b style="color:#f87171;">(> ¥500 触发店长HITL审批)</b>';
    warnEl.style.display = 'block';
  } else {
    hintEl.innerHTML = '<span style="color:#34d399;">(≤ ¥500 免审快速直派)</span>';
    warnEl.style.display = 'none';
  }
}

function handleActorChange(actor) {
  const badgeEl = document.getElementById('wo-actor-badge');
  if (actor === 'Executor') {
    badgeEl.className = 'wo-badge green';
    badgeEl.innerText = '角色: Executor (合法执行器)';
  } else {
    badgeEl.className = 'wo-badge purple';
    badgeEl.innerText = '角色: Sentry (只读监测 · 越权测试)';
  }
}

function regenerateIdempKey() {
  const rand = Math.random().toString(36).substring(2, 8).toUpperCase();
  document.getElementById('wo-idemp-key').value = `IDEMP-WO-20260918-${rand}`;
  appendWoLog('IDEMP', `已重新生成幂等凭据: IDEMP-WO-20260918-${rand}`);
}

function switchWoDataTab(tab) {
  document.getElementById('btn-tab-dbrecords').className = (tab === 'records') ? 'header-btn primary' : 'header-btn';
  document.getElementById('btn-tab-auditlog').className = (tab === 'audit') ? 'header-btn primary' : 'header-btn';
  document.getElementById('btn-tab-console').className = (tab === 'console') ? 'header-btn primary' : 'header-btn';

  document.getElementById('wo-tab-records').style.display = (tab === 'records') ? 'block' : 'none';
  document.getElementById('wo-tab-audit').style.display = (tab === 'audit') ? 'block' : 'none';
  document.getElementById('wo-tab-console').style.display = (tab === 'console') ? 'block' : 'none';
}

// Fetch live database counts & records
async function fetchLiveStatus() {
  try {
    const res = await fetch('/zhuguang/api/status');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    liveDbStatus = data;

    document.getElementById('wo-db-indicator').innerHTML = '<span style="color:var(--green)">● runtime.db 读写正常</span>';
    document.getElementById('wo-live-count').innerText = `${data.counts.workorders} 条落盘`;
    document.getElementById('app-live-count').innerText = `${data.counts.approvals} 条记录`;
    document.getElementById('audit-live-count').innerText = `${data.counts.audit_log} 笔存证`;

    // Render Workorders Table
    const tbody = document.getElementById('wo-tbody-records');
    if (data.workorders && data.workorders.length > 0) {
      tbody.innerHTML = data.workorders.map(wo => `
        <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
          <td style="padding:8px 12px; font-weight:700; color:var(--cyan);">${wo.workorder_id}</td>
          <td style="padding:8px 12px;">${wo.incident_id}</td>
          <td style="padding:8px 12px;">${wo.device_id}</td>
          <td style="padding:8px 12px; max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${wo.fault}</td>
          <td style="padding:8px 12px; color:var(--green); font-weight:700;">¥${parseFloat(wo.budget).toFixed(2)}</td>
          <td style="padding:8px 12px;">
            <span class="wo-badge ${wo.status === 'closed' ? 'green' : wo.status.includes('veto') ? 'red' : 'amber'}">${wo.status.toUpperCase()}</span>
          </td>
          <td style="padding:8px 12px; font-size:11px; color:var(--text-muted);">${wo.created_at.split('T')[1]?.substring(0,8) || wo.created_at}</td>
        </tr>
      `).join('');
    } else {
      tbody.innerHTML = `<tr><td colspan="7" style="padding:16px; text-align:center; color:var(--text-muted);">底层 SQLite 数据库暂无工单。请提交上方表单或点击场景一键派单！</td></tr>`;
    }

    // Render Audit Logs Table
    const tbodyAudit = document.getElementById('wo-tbody-audit');
    if (data.audit_logs && data.audit_logs.length > 0) {
      tbodyAudit.innerHTML = data.audit_logs.map(au => `
        <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
          <td style="padding:8px 12px; color:#c084fc;">${au.audit_id}</td>
          <td style="padding:8px 12px;">${au.request_id}</td>
          <td style="padding:8px 12px; font-weight:700; color:var(--cyan);">${au.actor}</td>
          <td style="padding:8px 12px;"><code>${au.tool_name}</code></td>
          <td style="padding:8px 12px;">coldchain-demo</td>
          <td style="padding:8px 12px; font-size:11px; color:var(--text-muted);">${au.created_at.split('T')[1]?.substring(0,8) || au.created_at}</td>
        </tr>
      `).join('');
    }

    appendWoLog('SQLITE', `同步底层数据库成功 · 工单: ${data.counts.workorders} 条, 审批: ${data.counts.approvals} 条, 审计: ${data.counts.audit_log} 笔`, 'green');
  } catch (err) {
    console.error('Failed to fetch status:', err);
    document.getElementById('wo-db-indicator').innerHTML = '<span style="color:#f87171;">离线/备用模式</span>';
    appendWoLog('WARN', `连接云端 API 失败或处于纯离线模式: ${err.message}`, 'amber');
  }
}

// Reset Database
async function resetLiveDatabase() {
  if (!confirm('确认清空云端 SQLite 中的测试工单与审批记录？')) return;
  try {
    const res = await fetch('/zhuguang/api/reset', { method: 'POST' });
    const data = await res.json();
    appendWoLog('RESET', data.message, 'amber');
    // Reset UI state
    currentWoRecord = null;
    currentApprovalId = null;
    document.getElementById('wo-status-badge').className = 'wo-badge cyan';
    document.getElementById('wo-status-badge').innerText = '待派发 (IDLE)';
    document.getElementById('wo-display-id').innerText = '#WO-STANDBY (尚未下发)';
    document.getElementById('wo-hitl-panel').style.display = 'none';
    document.getElementById('btn-tech-arrive').disabled = true;
    document.getElementById('btn-tech-finish').disabled = true;
    document.getElementById('btn-auditor-verify').disabled = true;
    updateStepsState(1);
    fetchLiveStatus();
  } catch (err) {
    alert('重置失败: ' + err.message);
  }
}

// Scenario Quick Loaders
function loadScenario(type) {
  currentScenarioMode = type;
  document.querySelectorAll('.scenario-card').forEach(c => c.style.borderColor = 'rgba(255,255,255,0.15)');

  if (type === 'happy_path') {
    document.getElementById('sc-card-happy').style.borderColor = 'var(--green)';
    document.getElementById('wo-fault').value = '压缩机启动电容老化失效 / 停转故障';
    document.getElementById('wo-budget').value = '420';
    document.getElementById('wo-actor-select').value = 'Executor';
    handleActorChange('Executor');
    handleBudgetInput(420);
    appendWoLog('SCENARIO', '🌟 载入正常标准流程：电容失效更换 (预算 ¥420 ≤ ¥500 免批)。系统将自动通过并下发！', 'green');
  } else if (type === 'hitl_gate') {
    document.getElementById('sc-card-hitl').style.borderColor = 'var(--red)';
    document.getElementById('wo-fault').value = '压缩机缸体抱死烧毁 / 需整体更换压缩机机组';
    document.getElementById('wo-budget').value = '850';
    document.getElementById('wo-actor-select').value = 'Executor';
    handleActorChange('Executor');
    handleBudgetInput(850);
    appendWoLog('SCENARIO', '⚠️ 载入高额预算刚性门禁场景：预算 ¥850 > ¥500。请点击【真实提交】实测店长刚性审批！', 'red');
  } else if (type === 'anti_self_verify') {
    document.getElementById('sc-card-asv').style.borderColor = 'var(--amber)';
    document.getElementById('wo-fault').value = '冷冻蒸发阀积冰卡滞 (鲜奶超温超标暴露)';
    document.getElementById('wo-budget').value = '460';
    document.getElementById('wo-actor-select').value = 'Executor';
    handleActorChange('Executor');
    handleBudgetInput(460);
    appendWoLog('SCENARIO', '🚨 载入物理反自验场景：冷柜修好降至4.5°C，但巴氏鲜奶超温暴露48分钟。实测 Auditor 一票否决！', 'amber');
  } else if (type === 'rbac_unauthorized') {
    document.getElementById('sc-card-rbac').style.borderColor = 'var(--purple)';
    document.getElementById('wo-fault').value = '非授权 Agent 越权写库尝试';
    document.getElementById('wo-budget').value = '420';
    document.getElementById('wo-actor-select').value = 'Sentry';
    handleActorChange('Sentry');
    handleBudgetInput(420);
    appendWoLog('SCENARIO', '🛡️ 载入 RBAC 越权拦截场景：以 Sentry 只读角色尝试调用 create_workorder 写库。实测 403 熔断！', 'purple');
  }
}

// Stepper Updater
function updateStepsState(activeStep, isVetoed = false) {
  for (let i = 1; i <= 6; i++) {
    const el = document.getElementById(`step-node-${i}`);
    if (!el) continue;
    el.className = 'wo-step';
    if (i < activeStep) {
      el.classList.add('completed');
    } else if (i === activeStep) {
      if (isVetoed) el.classList.add('vetoed');
      else el.classList.add('active');
    }
  }
}

// Submit Work Order
async function submitWorkOrder() {
  const storeId = document.getElementById('wo-store-id').value;
  const deviceId = document.getElementById('wo-device-id').value;
  const fault = document.getElementById('wo-fault').value;
  const budget = parseFloat(document.getElementById('wo-budget').value) || 0;
  const assignee = document.getElementById('wo-assignee').value;
  const actor = document.getElementById('wo-actor-select').value;
  const idempKey = document.getElementById('wo-idemp-key').value;

  appendWoLog('DISPATCH', `正在提交工单请求... 角色: ${actor}, 预算: ¥${budget}, 故障: ${fault}`, 'cyan');

  try {
    const payload = {
      store_id: storeId,
      device_id: deviceId,
      fault: fault,
      budget: budget,
      assignee: assignee,
      actor: actor,
      idempotency_key: idempKey,
      simulate_risk: (actor === 'Sentry') ? 'rbac_unauthorized' : (budget > 500 ? 'hitl_exceed_budget' : null)
    };

    const res = await fetch('/zhuguang/api/workorders/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    // 1. RBAC Blocked
    if (res.status === 403 || data.risk_type === 'rbac_blocked') {
      appendWoLog('RBAC_BLOCK', `🚨 [网关 403 熔断] 角色 ${actor} 无权调用 create_workorder！底层数据库 0 穿透！`, 'red');
      document.getElementById('wo-status-badge').className = 'wo-badge red';
      document.getElementById('wo-status-badge').innerText = 'RBAC 熔断 (403 FORBIDDEN)';
      alert(`🛡️ [RBAC 刚性拦截成功]\n${data.message || data.error}\n\n底层 SQLite 数据库 0 写入，安全审计日志已留存！`);
      fetchLiveStatus();
      return;
    }

    // 2. HITL Threshold Exceeded
    if (data.policy_blocked && data.risk_type === 'hitl_threshold_exceeded') {
      currentApprovalId = data.approval_id;
      appendWoLog('POLICY', `⚠️ [HITL 刚性门禁拦截] 预算 ¥${budget} > 门禁限额 ¥500！系统拒绝直接派单，已挂起生成店长审批单: ${data.approval_id}`, 'amber');
      document.getElementById('wo-status-badge').className = 'wo-badge amber';
      document.getElementById('wo-status-badge').innerText = '店长审批挂起 (APPROVAL_PENDING)';
      document.getElementById('wo-hitl-panel').style.display = 'block';
      document.getElementById('wo-hitl-appid').innerText = data.approval_id;
      document.getElementById('wo-display-id').innerText = '#WO-PENDING-APPROVAL';
      document.getElementById('wo-disp-budget').innerText = `¥${budget.toFixed(2)} (待审批)`;
      updateStepsState(2);
      fetchLiveStatus();
      return;
    }

    // 3. Normal Success (Happy Path)
    if (data.ok && data.workorder) {
      currentWoRecord = data.workorder;
      appendWoLog('SUCCESS', `✅ 工单下发成功！工单号: ${data.workorder.workorder_id}，已持久化写入底层 SQLite 数据库！`, 'green');
      document.getElementById('wo-status-badge').className = 'wo-badge cyan';
      document.getElementById('wo-status-badge').innerText = '已派单 (ASSIGNED)';
      document.getElementById('wo-display-id').innerText = '#' + data.workorder.workorder_id;
      document.getElementById('wo-disp-budget').innerText = `¥${data.workorder.budget.toFixed(2)}`;
      document.getElementById('wo-disp-fault').innerText = data.workorder.fault;
      document.getElementById('wo-hitl-panel').style.display = 'none';

      // Activate Technician Action Button
      document.getElementById('btn-tech-arrive').disabled = false;
      document.getElementById('btn-tech-finish').disabled = true;
      document.getElementById('btn-auditor-verify').disabled = true;

      updateStepsState(3);
      fetchLiveStatus();
    }
  } catch (err) {
    appendWoLog('ERROR', `工单提交异常: ${err.message}`, 'red');
    alert('提交异常: ' + err.message);
  }
}

// Store Manager Decision
async function decideApproval(decision) {
  if (!currentApprovalId) return;
  const budget = parseFloat(document.getElementById('wo-budget').value) || 850;
  const reason = (decision === 'approved') ? '店长在线签署同意，紧急调拨资金换件' : '预算过高，责令重选经济型维修方案';

  appendWoLog('HITL_DECIDE', `店长执行审批决策: ${decision.toUpperCase()} · 意见: ${reason}`, decision === 'approved' ? 'green' : 'red');

  try {
    const res = await fetch('/zhuguang/api/approvals/decide', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        approval_id: currentApprovalId,
        decision: decision,
        reason: reason,
        budget: budget,
        store_id: document.getElementById('wo-store-id').value,
        device_id: document.getElementById('wo-device-id').value,
        fault: document.getElementById('wo-fault').value,
        assignee: document.getElementById('wo-assignee').value,
      })
    });
    const data = await res.json();

    if (decision === 'rejected') {
      document.getElementById('wo-status-badge').className = 'wo-badge red';
      document.getElementById('wo-status-badge').innerText = '审批驳回 (REJECTED)';
      document.getElementById('wo-hitl-panel').innerHTML = `
        <div style="color:#f87171; font-weight:700; font-size:13px; margin-bottom:4px;">🚫 [店长驳回/超时] 工单被刚性拦截，0 写入底层数据库！</div>
        <div style="font-size:12px; color:#fee2e2;">
          <b>这正是此前 Matrix 聊天中工单不存在的根本原因</b>：风控系统有效运转，未经审批的高额开支绝不伪造落库！
        </div>
      `;
      appendWoLog('POLICY', '🚫 [风控刚性阻断] 审批驳回，底层的 workorders 表保持 0 写入！阻断违规大额维修款！', 'red');
      updateStepsState(2, true);
      fetchLiveStatus();
    } else {
      currentWoRecord = data.workorder;
      document.getElementById('wo-status-badge').className = 'wo-badge cyan';
      document.getElementById('wo-status-badge').innerText = '已派单 (ASSIGNED)';
      document.getElementById('wo-display-id').innerText = '#' + data.workorder.workorder_id;
      document.getElementById('wo-hitl-panel').style.display = 'none';
      document.getElementById('btn-tech-arrive').disabled = false;
      appendWoLog('SUCCESS', `✅ 店长授权通过！大额工单 ${data.workorder.workorder_id} 正式落库！`, 'green');
      updateStepsState(3);
      fetchLiveStatus();
    }
  } catch (err) {
    appendWoLog('ERROR', '审批决策提交失败: ' + err.message, 'red');
  }
}

// Technician Progress Work Order
async function progressWorkOrder(status) {
  if (!currentWoRecord) return;
  const wid = currentWoRecord.workorder_id;

  try {
    const res = await fetch('/zhuguang/api/workorders/progress', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workorder_id: wid,
        status: status,
        evidence: { timestamp: new Date().toISOString(), tech: '李师傅 (资质冷链工程师)' }
      })
    });
    const data = await res.json();

    if (status === 'in_progress') {
      document.getElementById('wo-status-badge').className = 'wo-badge amber';
      document.getElementById('wo-status-badge').innerText = '维修施工中 (IN_PROGRESS)';
      appendWoLog('WORKER', `👨‍🔧 维修师傅已到场打卡，开始检修电路并拆换电容/元器件...`, 'amber');
      document.getElementById('btn-tech-arrive').disabled = true;
      document.getElementById('btn-tech-finish').disabled = false;
      updateStepsState(4);
    } else if (status === 'pending_verification') {
      document.getElementById('wo-status-badge').className = 'wo-badge purple';
      document.getElementById('wo-status-badge').innerText = '待验真 (PENDING_VERIFY)';
      appendWoLog('WORKER', `✅ 施工完毕！师傅提交完工报告：压缩机已重新转动，出风口降温中。工单进入独立验真阶段！`, 'purple');
      document.getElementById('btn-tech-finish').disabled = true;
      document.getElementById('btn-auditor-verify').disabled = false;
      updateStepsState(5);
    }
    fetchLiveStatus();
  } catch (err) {
    appendWoLog('ERROR', '更新工单状态异常: ' + err.message, 'red');
  }
}

// Auditor Independent Dual-Gate Verification
async function verifyWorkOrder() {
  if (!currentWoRecord) return;
  const wid = currentWoRecord.workorder_id;
  const isAntiSelfVerify = (currentScenarioMode === 'anti_self_verify');

  appendWoLog('AUDITOR', `🛡️ Auditor 启动带外独立验真... (防伪闭环核查)`, 'cyan');

  try {
    const res = await fetch('/zhuguang/api/workorders/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workorder_id: wid,
        condition: isAntiSelfVerify ? 'anti_self_verify_spoiled' : 'normal',
        device_temp: isAntiSelfVerify ? 4.5 : 4.2,
        exposure_minutes: isAntiSelfVerify ? 48 : 22
      })
    });
    const data = await res.json();

    if (data.verification === 'PASS') {
      document.getElementById('wo-status-badge').className = 'wo-badge green';
      document.getElementById('wo-status-badge').innerText = '已验真闭环 (CLOSED)';
      document.getElementById('wo-disp-pos').innerHTML = '<span style="color:var(--green)">解封正常销售 (RELEASED)</span>';
      document.getElementById('btn-auditor-verify').disabled = true;
      appendWoLog('AUDITOR', `✅ [双门独立验真通过] 物理温度 4.2°C 达标，累计超温暴露积温仅 22m (<30m限额)。POS 销售锁已解除，工单合规关闭！`, 'green');
      updateStepsState(6);
    } else {
      document.getElementById('wo-status-badge').className = 'wo-badge red';
      document.getElementById('wo-status-badge').innerText = '反自验一票否决 (VETOED)';
      document.getElementById('wo-disp-pos').innerHTML = '<span style="color:var(--red)">永久停售锁定 (LOCKED)</span>';
      document.getElementById('btn-auditor-verify').disabled = true;
      appendWoLog('AUDITOR', `🚨 [物理反自验一票否决] 师傅虽然修好冷柜(4.5°C)，但鲜奶累计超温暴露达 48 分钟 (>30m安全极限)，判定不可逆变质！一票否决解封申请，巴氏鲜奶批次强制标记为报废 (disposed)！`, 'red');
      updateStepsState(5, true);
    }
    fetchLiveStatus();
  } catch (err) {
    appendWoLog('ERROR', 'Auditor 验真异常: ' + err.message, 'red');
  }
}

// Auto load status on ready
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(fetchLiveStatus, 500);
});
"""

def main():
    content = HTML_PATH.read_text(encoding="utf-8")
    
    # 1. Insert CSS before </style>
    if "/* ==================== WORK ORDER & RISK CONTROL PLAYGROUND STYLES ==================== */" not in content:
        content = content.replace("</style>", WO_CSS + "\n</style>", 1)
        print("Inserted WO_CSS")
        
    # 2. Insert Header button
    header_btn_html = """      <button class="header-btn primary" onclick="switchMainTab('workorder')" style="background:linear-gradient(135deg, #059669, #0284c7); border-color:#34d399; color:#fff; cursor:pointer;">
        📋 真实工单与风控演练
      </button>\n"""
    if "switchMainTab('workorder')" not in content:
        content = content.replace('<div class="header-actions">', '<div class="header-actions">\n' + header_btn_html, 1)
        print("Inserted Header Button")
        
    # 3. Insert Nav Tab in main-nav-tabs
    nav_tab_html = """    <button class="nav-tab-btn active" onclick="switchMainTab('workorder')">
      📋 真实工单与风控演练台
      <span class="badge-pill" style="background:rgba(16,185,129,0.25); color:#34d399; font-weight:700;">端到端全流程 · 4大风控实测</span>
    </button>\n"""
    
    # Deactivate 'demo' button
    content = re.sub(r'<button class="nav-tab-btn active" onclick="switchMainTab\(\'demo\'\)">', r'<button class="nav-tab-btn" onclick="switchMainTab(\'demo\')">', content)
    
    if "switchMainTab('workorder')" in content:
        # Check if tab exists in nav
        if '<button class="nav-tab-btn active" onclick="switchMainTab(\'workorder\')">' not in content:
            content = content.replace('<nav class="main-nav-tabs">', '<nav class="main-nav-tabs">\n' + nav_tab_html, 1)
            print("Inserted Nav Tab")

    # 4. Deactivate view-demo section and insert view-workorder section
    content = content.replace('<section id="view-demo" class="view-section active">', '<section id="view-demo" class="view-section">')
    
    if 'id="view-workorder"' not in content:
        # Insert before view-video or after </nav>
        content = content.replace('</nav>', '</nav>\n' + WO_SECTION, 1)
        print("Inserted WO_SECTION")
        
    # 5. Insert JS before </script>
    if "// ==================== WORK ORDER & RISK CONTROL PLAYGROUND JS ====================" not in content:
        content = content.replace('</script>', WO_JS + '\n</script>', 1)
        print("Inserted WO_JS")
        
    HTML_PATH.write_text(content, encoding="utf-8")
    print("Successfully patched delivery_portal_html_content.html!")

if __name__ == "__main__":
    main()
