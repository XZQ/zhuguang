#!/usr/bin/env python3
"""Build Native Interactive Web Application for Defense Manual (No PDF needed, 100% Web Native)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = ROOT / "scripts" / "build_delivery_portal.py"
STANDALONE_HTML_PATH = ROOT / "dist" / "delivery-portal" / "defense.html"

# Define the full native HTML content for the defense dossier
DOSSIER_HTML = """
    <div class="dossier-wrap" style="color:var(--text); max-width: 1100px; margin: 0 auto; space-y: 24px;">
      
      <!-- Top Action & Navigation Banner -->
      <div style="background: linear-gradient(135deg, rgba(3,105,161,0.2) 0%, rgba(15,23,42,0.8) 100%); border: 1px solid rgba(56,189,248,0.3); border-radius: 14px; padding: 20px; margin-bottom: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="background:#0284c7; color:#fff; font-size:11px; font-weight:800; padding:2px 8px; border-radius:4px;">复赛答辩专属</span>
              <h2 style="font-size:22px; font-weight:800; color:#fff; margin:0;">
                📖 2026 GOAI 复赛答辩图文全景大纲 (12大章节速查宝典)
              </h2>
            </div>
            <p style="font-size:13px; color:var(--text-secondary); margin-top:6px; margin-bottom:0;">
              纯网页原生交互排版 · 涵盖立项痛点、512台设备态势、五层架构、5-Agent 协同、双重状态模型、3分钟发言稿与 Q&A 攻防库
            </p>
          </div>
          <div style="display:flex; gap:10px; flex-wrap:wrap;">
            <a href="./defense.html" target="_blank" class="demo-btn" style="background:#0284c7; color:#fff; text-decoration:none; padding:8px 14px; font-size:12px; font-weight:700; border-radius:8px; display:flex; align-items:center; gap:6px;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              全屏独立大纲网页
            </a>
            <a href="./ppt/" target="_blank" class="demo-btn secondary" style="text-decoration:none; padding:8px 14px; font-size:12px; border-radius:8px; display:flex; align-items:center; gap:6px;">
              📑 打开 15 页方案 PPT
            </a>
            <button onclick="switchMainTab('demo')" class="demo-btn secondary" style="padding:8px 14px; font-size:12px; border-radius:8px; display:flex; align-items:center; gap:6px;">
              ⚡️ 切回 1 分钟 Demo 演练
            </button>
          </div>
        </div>

        <!-- Sticky Quick Chapter Links -->
        <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:16px; padding-top:14px; border-top:1px solid rgba(255,255,255,0.1); font-size:11.5px;">
          <a href="#d-ch1" style="color:var(--cyan); background:rgba(56,189,248,0.1); padding:3px 8px; border-radius:4px; text-decoration:none;">1. 立项痛点</a>
          <a href="#d-ch2" style="color:var(--cyan); background:rgba(56,189,248,0.1); padding:3px 8px; border-radius:4px; text-decoration:none;">2. 商业收益</a>
          <a href="#d-ch3" style="color:var(--cyan); background:rgba(56,189,248,0.1); padding:3px 8px; border-radius:4px; text-decoration:none;">3. 512设备大盘</a>
          <a href="#d-ch4" style="color:var(--cyan); background:rgba(56,189,248,0.1); padding:3px 8px; border-radius:4px; text-decoration:none;">4. 五层架构</a>
          <a href="#d-ch5" style="color:var(--cyan); background:rgba(56,189,248,0.1); padding:3px 8px; border-radius:4px; text-decoration:none;">5. 5-Agent协同</a>
          <a href="#d-ch6" style="color:var(--cyan); background:rgba(56,189,248,0.1); padding:3px 8px; border-radius:4px; text-decoration:none;">6. 技术亮点</a>
          <a href="#d-ch7" style="color:var(--cyan); background:rgba(56,189,248,0.1); padding:3px 8px; border-radius:4px; text-decoration:none;">7. 传统动环结合</a>
          <a href="#d-ch8" style="color:var(--cyan); background:rgba(56,189,248,0.1); padding:3px 8px; border-radius:4px; text-decoration:none;">8. 跨行业复制</a>
          <a href="#d-ch9" style="color:#fde047; background:rgba(234,179,8,0.15); padding:3px 8px; border-radius:4px; text-decoration:none; font-weight:700;">★ 9. 3分钟发言稿</a>
          <a href="#d-ch10" style="color:#f87171; background:rgba(239,68,68,0.15); padding:3px 8px; border-radius:4px; text-decoration:none; font-weight:700;">★ 10. 1分钟Demo表</a>
          <a href="#d-ch11" style="color:#a78bfa; background:rgba(167,139,250,0.15); padding:3px 8px; border-radius:4px; text-decoration:none; font-weight:700;">★ 11. 评委Q&A</a>
          <a href="#d-ch12" style="color:var(--green); background:rgba(16,185,129,0.1); padding:3px 8px; border-radius:4px; text-decoration:none;">12. 自检预案</a>
        </div>
      </div>

      <!-- CHAPTER 1 -->
      <section id="d-ch1" style="background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; margin-bottom:20px;">
        <h3 style="color:#38bdf8; font-size:16px; margin-top:0; display:flex; align-items:center; gap:8px;">
          <span>01</span> 为什么做这个项目？痛点透视与传统监控三大致命盲区
        </h3>
        <p style="font-size:13px; color:var(--text-secondary); line-height:1.7;">
          连锁便利店（如 7-Eleven、罗森、美宜佳）和生鲜门店高度依赖物理冷链。但现有的动环系统普遍存在三大断层：
        </p>
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:12px; margin-top:12px;">
          <div style="background:rgba(239,68,68,0.06); border:1px solid rgba(239,68,68,0.3); border-radius:8px; padding:12px;">
            <b style="color:#fca5a5; font-size:13px;">1. 告警风暴与假闭环（如智感温盾）</b>
            <p style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
              传统监控只做单点硬阈值报警，全网每天上千条报警风暴（现实中单日活跃告警达 608 条），店员麻木疲劳；系统提供的唯一处置方式竟然只有敷衍的【标记已解决】按钮，形成“告警已读，事故未消”的严重形式主义。
            </p>
          </div>
          <div style="background:rgba(239,68,68,0.06); border:1px solid rgba(239,68,68,0.3); border-radius:8px; padding:12px;">
            <b style="color:#fca5a5; font-size:13px;">2. 设备恢复 ≠ 商品安全（行业最大盲区）</b>
            <p style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
              冷柜跳闸 2 小时后重新来电，温度降回了 4.8°C。传统系统显示设备变绿，但柜内巴氏鲜奶在常温下超温暴露超过 30 分钟早已不可逆变质！现有系统缺乏商品暴露时长积分追踪，导致变质牛奶流向收银台。
            </p>
          </div>
          <div style="background:rgba(239,68,68,0.06); border:1px solid rgba(239,68,68,0.3); border-radius:8px; padding:12px;">
            <b style="color:#fca5a5; font-size:13px;">3. 执行与验收一体（自验漏洞）</b>
            <p style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
              报修、维修、验收由同一个人或同一家外包商闭环，“执行者自己宣布自己修好了”就能结案，缺乏独立第三方查证客观事实的制约机制。
            </p>
          </div>
        </div>
      </section>

      <!-- CHAPTER 2 -->
      <section id="d-ch2" style="background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; margin-bottom:20px;">
        <h3 style="color:#38bdf8; font-size:16px; margin-top:0; display:flex; align-items:center; gap:8px;">
          <span>02</span> 项目核心定位与量化商业收益（四大 ROI 维度）
        </h3>
        <p style="font-size:13px; color:var(--text-secondary); line-height:1.7;">
          <b>核心定位</b>：交付的不是一条冷冰冰的告警日志，而是一份<b>“责任清晰、证据完备、通过安全门禁的五阶段闭环包”</b>。
        </p>
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:10px; margin-top:12px;">
          <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.3); border-radius:8px; padding:12px; text-align:center;">
            <div style="font-size:24px; font-weight:900; color:var(--green); font-family:var(--font-mono);">0 容忍</div>
            <div style="font-size:12px; font-weight:700; color:#fff; margin-top:4px;">食品安全事故发生率</div>
            <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">20s 自动施加 POS 停售锁</div>
          </div>
          <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.3); border-radius:8px; padding:12px; text-align:center;">
            <div style="font-size:24px; font-weight:900; color:var(--green); font-family:var(--font-mono);">60%+</div>
            <div style="font-size:12px; font-weight:700; color:#fff; margin-top:4px;">精细化定损减亏比例</div>
            <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">鲜奶报损 · 熟食调拨放行</div>
          </div>
          <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.3); border-radius:8px; padding:12px; text-align:center;">
            <div style="font-size:24px; font-weight:900; color:var(--green); font-family:var(--font-mono);">90%+</div>
            <div style="font-size:12px; font-weight:700; color:#fff; margin-top:4px;">时序告警降噪率</div>
            <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">Westgard 法则过滤开门抖动</div>
          </div>
          <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.3); border-radius:8px; padding:12px; text-align:center;">
            <div style="font-size:24px; font-weight:900; color:var(--green); font-family:var(--font-mono);">100%</div>
            <div style="font-size:12px; font-weight:700; color:#fff; margin-top:4px;">合规穿透审计率</div>
            <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">SHA-256 哈希 + 只增审计</div>
          </div>
        </div>
      </section>

      <!-- CHAPTER 3 -->
      <section id="d-ch3" style="background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; margin-bottom:20px;">
        <h3 style="color:#38bdf8; font-size:16px; margin-top:0; display:flex; align-items:center; gap:8px;">
          <span>03</span> 多门店多设备分布式网络矩阵（128 店 · 512 台设备）
        </h3>
        <p style="font-size:13px; color:var(--text-secondary); line-height:1.7;">
          真实连锁网络包含 128 家门店、512 台多温区冷链设备。Sentry Agent 以 30 秒周期轮询全网，排除正常设备波动，精准锁定异常单柜：
        </p>
        <div style="background:rgba(0,0,0,0.3); border:1px solid var(--border-subtle); border-radius:8px; padding:12px; font-size:12px; font-family:var(--font-mono);">
          • <b>全网态势</b>：S01 深圳科技园店 (6台全绿) · S02 广州珠江新城店 (4台全绿) · S04 佛山千灯湖店 (5台全绿) · <b>S03 广州天河店 (1柜失温中)</b><br>
          • <b>S03 店内矩阵</b>：1号鲜奶冷藏柜 (9.6°C 🚨 失温) · 2号冰淇淋冷冻柜 (-18.4°C 🟢) · 3号鲜食保温柜 (62.5°C 🟢) · 4号饮料冷藏柜 (3.8°C 🟢)<br>
          • <b>核心价值</b>：Sentry 精准锁定 S03 店 1 号柜发起停售与闭环，其余 511 台正常设备丝毫不受影响，保证全网平稳运营！
        </div>
      </section>

      <!-- CHAPTER 4 & 5 -->
      <section id="d-ch4" style="background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; margin-bottom:20px;">
        <h3 style="color:#38bdf8; font-size:16px; margin-top:0; display:flex; align-items:center; gap:8px;">
          <span>04 & 05</span> 技术方案与 5-Agent 协同制衡设计（三权分立）
        </h3>
        <div style="overflow-x:auto;">
          <table class="tbl" style="width:100%; font-size:12px; margin-top:8px;">
            <thead>
              <tr style="border-bottom:1px solid rgba(255,255,255,0.1); color:var(--text-muted);">
                <th style="padding:8px; text-align:left;">Agent 角色</th>
                <th style="padding:8px; text-align:left;">权限级别</th>
                <th style="padding:8px; text-align:left;">核心职责与输入输出</th>
                <th style="padding:8px; text-align:left;">硬性安全边界约束</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding:8px; font-weight:700; color:#fff;">Orchestrator</td>
                <td style="padding:8px; color:#38bdf8;">Leader (无写权)</td>
                <td style="padding:8px;">全局目标拆解、五阶段状态流转推进、复盘沉淀</td>
                <td style="padding:8px; color:#fca5a5;">无领域写权限，严禁越权修改任何设备或库存数据</td>
              </tr>
              <tr>
                <td style="padding:8px; font-weight:700; color:#fff;">Sentry</td>
                <td style="padding:8px; color:var(--green);">L0 只读权限</td>
                <td style="padding:8px;">30s 并行巡检 512 台设备，Westgard 去噪，识别失温</td>
                <td style="padding:8px; color:#fca5a5;">无执行权，仅能向总控发出 request_containment 遏制请求</td>
              </tr>
              <tr>
                <td style="padding:8px; font-weight:700; color:#fff;">Diagnoser</td>
                <td style="padding:8px; color:var(--green);">L0 只读权限</td>
                <td style="padding:8px;">排查门磁/除霜，锁定压缩机；积分计算商品超温暴露时长</td>
                <td style="padding:8px; color:#fca5a5;">无执行权，严禁把相关性作为确定事实，仅出具建议</td>
              </tr>
              <tr>
                <td style="padding:8px; font-weight:700; color:#fff;">Executor</td>
                <td style="padding:8px; color:#fcd34d;">L1/L2 受控写</td>
                <td style="padding:8px;">下发 POS 停售锁、派发急修工单、生成报损审批</td>
                <td style="padding:8px; color:#fca5a5;">受 Policy 拦截，全量写携带幂等键；严禁自验与越权付款</td>
              </tr>
              <tr>
                <td style="padding:8px; font-weight:700; color:#fff;">Auditor</td>
                <td style="padding:8px; color:var(--red);">独立稽核员</td>
                <td style="padding:8px;">独立开辟干净上下文，重查两套事实，出具放行门禁判定</td>
                <td style="padding:8px; color:#fca5a5;"><b>一票否决权！</b>执行者不能自证成功，商品变质强制阻断</td>
              </tr>
              <tr>
                <td style="padding:8px; font-weight:700; color:#fff;">Policy / Guard</td>
                <td style="padding:8px; color:#fcd34d;">安全门禁</td>
                <td style="padding:8px;">拦截大额派修与商品报损，挂起触发店长移动端审批</td>
                <td style="padding:8px; color:#fca5a5;">未经店长授权，Executor 无法获得执行令牌</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- CHAPTER 6 -->
      <section id="d-ch6" style="background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; margin-bottom:20px;">
        <h3 style="color:#38bdf8; font-size:16px; margin-top:0; display:flex; align-items:center; gap:8px;">
          <span>06</span> 五大硬核技术亮点与底层创新壁垒
        </h3>
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:10px;">
          <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border-subtle); border-radius:8px; padding:12px;">
            <b style="color:#fff; font-size:12.5px;">1. 双重状态解耦模型（行业首创）</b>
            <p style="font-size:11.5px; color:var(--text-secondary); margin-top:3px;">
              显式解耦<b>物理设备状态（Device State）</b>与<b>商品资产安全状态（Asset State）</b>。打破“设备修好即事件结案”的传统漏洞。
            </p>
          </div>
          <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border-subtle); border-radius:8px; padding:12px;">
            <b style="color:#fff; font-size:12.5px;">2. 反自验独立稽核机制（Anti-Self-Verification）</b>
            <p style="font-size:11.5px; color:var(--text-secondary); margin-top:3px;">
              Auditor 拥有独立于执行者的全新上下文和专用只读接口，具备<b>一票否决权（阻断放行与回开 Reopen）</b>，消灭模型自证幻觉。
            </p>
          </div>
          <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border-subtle); border-radius:8px; padding:12px;">
            <b style="color:#fff; font-size:12.5px;">3. 临床级 Westgard 质控法则时序去噪</b>
            <p style="font-size:11.5px; color:var(--text-secondary); margin-top:3px;">
              将医学实验室 Westgard 法则（±3SD 阈值线、均值漂移）引入零售时序，消除 90% 虚假报警，精准识别持续失温。
            </p>
          </div>
          <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border-subtle); border-radius:8px; padding:12px;">
            <b style="color:#fff; font-size:12.5px;">4. Skill 九要素标准化契约治理</b>
            <p style="font-size:11.5px; color:var(--text-secondary); margin-top:3px;">
              6 个 P0 Skill 严格满足参赛九要素规范，解耦输入输出 Schema 与 MCP 工具，具备跨行业即插即用迁移能力。
            </p>
          </div>
          <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border-subtle); border-radius:8px; padding:12px;">
            <b style="color:#fff; font-size:12.5px;">5. 金融级不可篡改审计流</b>
            <p style="font-size:11.5px; color:var(--text-secondary); margin-top:3px;">
              底层收回 `audit_log` 的 UPDATE/DELETE 权限，只允许 INSERT；全量操作附带客户端生成的 `idempotency_key`，杜绝重复派修扣款。
            </p>
          </div>
        </div>
      </section>

      <!-- CHAPTER 9: 3-MIN SPEECH (HIGH IMPACT) -->
      <section id="d-ch9" style="background: linear-gradient(180deg, rgba(234,179,8,0.1) 0%, rgba(15,23,42,0.9) 100%); border: 1.5px solid #eab308; border-radius:14px; padding:20px; margin-bottom:20px; box-shadow: 0 0 20px rgba(234,179,8,0.15);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
          <h3 style="color:#fde047; font-size:18px; margin:0; display:flex; align-items:center; gap:8px;">
            <span>★ 09</span> 【3 分钟项目陈述】终极实战逐字发言稿（掐秒精确到秒 · 答辩必背）
          </h3>
          <span style="font-size:12px; font-weight:700; color:#fde047; font-family:var(--font-mono);">配图：15 页 PPT 全屏翻页</span>
        </div>

        <div style="space-y: 12px; font-size: 13px; line-height: 1.8;">
          <div style="background:rgba(0,0,0,0.4); border-left:4px solid #eab308; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="color:#fde047; font-weight:700; font-size:12.5px; margin-bottom:4px;">
              00:00 - 00:40（痛点聚焦 · 40秒 · PPT 第 1~3 页）
            </div>
            <div style="color:#f8fafc;">
              “各位评委老师下午好！我是第 13 队逐光队，今天汇报的作品是面向连锁门店的物理异常闭环基础设施——<b>店巡 Agent</b>。<br>
              在便利店冷链运维中，冷柜失温看似简单，但现有方案存在三个致命缺陷：<br>
              第一，<b>告警风暴与假闭环</b>：传统监控只做单点硬报警，全网每天上千条告警让店员疲劳麻木，处置手段只有一个敷衍的‘标记已解决’，这是典型的‘告警已读，事故未消’；<br>
              第二，<b>双重状态严重脱节</b>：<b>设备恢复不等于商品安全！</b>冷柜修好了、温度降回去了，但超温暴露超标的鲜牛奶依然已经变质；<br>
              第三，<b>缺乏职责制衡</b>：派工、维修、验收常由同一人自验自放。<br>
              因此，店巡 Agent 解决的不是单纯发告警，而是<b>让异常从发现、遏制、诊断，真正走向独立稽核与安全闭环</b>。”
            </div>
          </div>

          <div style="background:rgba(0,0,0,0.4); border-left:4px solid #38bdf8; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="color:#38bdf8; font-weight:700; font-size:12.5px; margin-bottom:4px;">
              00:40 - 01:40（方案与多 Agent 协同 · 60秒 · PPT 第 4~8 页）
            </div>
            <div style="color:#f8fafc;">
              “在架构设计上，我们基于赛道指定的 <b>AgentTeams v1.2.3</b> 基础设施，构建了 1 个 Team Leader + 5 个业务 Worker 的拓扑体系，坚持严格的<b>职责分离与权限隔离</b>：<br>
              • <b>Orchestrator（总控编排）</b>：负责全局目标拆解与状态推进，只调度协调，没有任何领域写权限；<br>
              • <b>Sentry（全网守卫 · 只读）</b>：以 30 秒周期并行巡检全网 128 店 512 台设备，引入 Westgard 质控法则时序去噪，精准锁定异常单柜，发起紧急遏制；<br>
              • <b>Diagnoser（根因诊断 · 只读）</b>：排查门磁与除霜，锁定压缩机故障，同时积分计算每批次商品超温暴露时长；<br>
              • <b>Executor（受控执行 · 受控写）</b>：下发 POS 停售锁、派发急修工单，全量写操作强制挂载幂等键；<br>
              • <b>Auditor（独立稽核 · 核心红线守门员）</b>：<b>执行者不能自证成功！</b> Auditor 必须独立调用接口重查设备与商品双重事实，只要商品变质，坚决阻断放行或回开事件！”
            </div>
          </div>

          <div style="background:rgba(0,0,0,0.4); border-left:4px solid var(--green); padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="color:var(--green); font-weight:700; font-size:12.5px; margin-bottom:4px;">
              01:40 - 02:20（技术亮点与安全边界 · 40秒 · PPT 第 9~12 页）
            </div>
            <div style="color:#f8fafc;">
              “在底层 Agent Infra 创新与安全防御上，我们重点构筑了三层防线：<br>
              • <b>有状态业务中枢（IncidentService）</b>：定义了严格的五阶段业务状态机，支持大模型断线重连与故障原子恢复；<br>
              • <b>高风险人机协同（HITL）</b>：维修预算超限或商品强制报损时，Policy 门禁自动拦截并挂起，推送店长移动端一键核准，杜绝模型越权；<br>
              • <b>金融级防篡改审计</b>：在数据库底层剥夺 audit_log 的 UPDATE 和 DELETE 权限，保证全链路操作‘只增不改’，完美契合食品安全合规溯源。”
            </div>
          </div>

          <div style="background:rgba(0,0,0,0.4); border-left:4px solid #a78bfa; padding:12px 16px; border-radius:0 8px 8px 0;">
            <div style="color:#a78bfa; font-weight:700; font-size:12.5px; margin-bottom:4px;">
              02:20 - 03:00（可验证价值与规模化复制 · 40秒 · PPT 第 13~15 页）
            </div>
            <div style="color:#f8fafc;">
              “逐光项目拒绝空洞的概念设计，所有能力均已在生产级环境中严密验证：<br>
              • <b>真实生产集群</b>：部署于广州 Linux 服务器，接入阿里百炼 qwen3.8-max，通过 Matrix 协议驱动实机多 Worker；<br>
              • <b>确定性证据链</b>：内置 87 个自动化测试用例，覆盖 6 大正常与对抗场景，沉淀了 45 份不可篡改的 Evidence 证据包和 26 条 Trace 链路，违规放行率为 0；<br>
              • <b>广泛的复用能力</b>：规范治理 6 大核心 P0 Skill，不仅能管便利店冷柜，更能无缝迁移至<b>医药疫苗冷链、中央厨房 HACCP 品控与数据中心动环</b>！<br>
              下面进入 1 分钟实机协同 Demo 演示！”
            </div>
          </div>
        </div>
      </section>

      <!-- CHAPTER 10: 1-MIN DEMO TABLE (HIGH IMPACT) -->
      <section id="d-ch10" style="background:var(--card); border: 1.5px solid var(--red); border-radius:14px; padding:20px; margin-bottom:20px;">
        <h3 style="color:#f87171; font-size:18px; margin-top:0; display:flex; align-items:center; gap:8px;">
          <span>★ 10</span> 【1 分钟 Demo 演示】60 秒全屏联动操作与解说词全对照表
        </h3>
        <p style="font-size:12.5px; color:var(--text-secondary); margin-bottom:10px;">
          投屏打开指挥中心主页第一栏，点击绿色 <b>【一键演练 (60s)】</b>，对照执行以下台词：
        </p>
        <div style="overflow-x:auto;">
          <table class="tbl" style="width:100%; font-size:12px;">
            <thead>
              <tr style="border-bottom:1px solid rgba(255,255,255,0.1); color:var(--text-muted);">
                <th style="padding:8px; text-align:left; width:70px;">时间轴</th>
                <th style="padding:8px; text-align:left; width:220px;">屏幕画面视觉联动</th>
                <th style="padding:8px; text-align:left;">答辩解说台词（核心得分点）</th>
                <th style="padding:8px; text-align:left; width:120px;">考核点对应</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding:8px; font-weight:700; color:#38bdf8;">00-10s</td>
                <td style="padding:8px;">全网 128 店扫描，锁定 S03 店 1 号柜（9.6°C 标红）</td>
                <td style="padding:8px;">“Sentry 巡检全网 512 台设备，自动过滤常规开门波动，精准捕捉到 S03 天河店 1 号鲜奶柜突破 8°C 告警线，排除断流，向总控发出紧急遏制请求。”</td>
                <td style="padding:8px; color:#38bdf8;">关键链路 · 异常发现</td>
              </tr>
              <tr>
                <td style="padding:8px; font-weight:700; color:#fcd34d;">10-20s</td>
                <td style="padding:8px;">1 号设备打上停售锁，图表弹出【🔒 停售锁已下发】</td>
                <td style="padding:8px;">“食品安全第一！Executor 立即下发 L1 预授权动作，通过 MCP 切断 POS 收银结算，防止潜在变质品流向顾客。”</td>
                <td style="padding:8px; color:#fcd34d;">Agent 协作 · 遏制</td>
              </tr>
              <tr>
                <td style="padding:8px; font-weight:700; color:#fcd34d;">20-30s</td>
                <td style="padding:8px;">状态更新为压缩机故障，超温暴露累积至 35min</td>
                <td style="padding:8px;">“Diagnoser 综合排查门磁与除霜，锁定压缩机电容老化（置信度 0.94）；同时计算鲜奶已超温暴露 35 分钟，建议强制报损，熟食调拨备用冷柜。”</td>
                <td style="padding:8px; color:#fcd34d;">多源诊断 · 资产定损</td>
              </tr>
              <tr>
                <td style="padding:8px; font-weight:700; color:#38bdf8;">30-40s</td>
                <td style="padding:8px;">技工到店换件，<b>折线快速俯冲降温至 7.2°C</b></td>
                <td style="padding:8px;">“维修预算触发店长手机端一键审批（HITL）。冷修技工到店换件，冷柜重新制冷，温度快速向下回落！”</td>
                <td style="padding:8px; color:#38bdf8;">HITL 审批 · 闭环降温</td>
              </tr>
              <tr style="background:rgba(239,68,68,0.08);">
                <td style="padding:8px; font-weight:900; color:var(--red);">40-50s<br>🔥高光</td>
                <td style="padding:8px;">设备降温至 4.8°C 变绿，图表弹出深红徽章：<br><b>【🛡️ Auditor: 鲜奶超温变质阻断放行!】</b></td>
                <td style="padding:8px; color:#fca5a5;"><b>“请评委老师重点关注核心安全红线：冷柜虽已降回 4.8°C，但 Auditor 独立重查判定鲜奶暴露 42 分钟已不可逆变质，坚决阻断放行、强制报损！彻底终结执行者自验自放！”</b></td>
                <td style="padding:8px; color:var(--red); font-weight:700;">核心红线阻断 · 独立稽核</td>
              </tr>
              <tr>
                <td style="padding:8px; font-weight:700; color:var(--green);">50-60s</td>
                <td style="padding:8px;">鲜奶销毁熟食放行，<b>左上角 S03 店瞬间变绿</b></td>
                <td style="padding:8px;">“熟食转移合规放行，变质鲜奶销毁报损。Orchestrator 沉淀电容老化知识条目，事件安全关闭，全网重归全绿守护，完成高可靠闭环！”</td>
                <td style="padding:8px; color:var(--green);">知识沉淀 · 安全关闭</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- CHAPTER 11: Q&A DEFENSE (HIGH IMPACT) -->
      <section id="d-ch11" style="background:var(--card); border: 1.5px solid #a78bfa; border-radius:14px; padding:20px; margin-bottom:20px;">
        <h3 style="color:#c4b5fd; font-size:18px; margin-top:0; display:flex; align-items:center; gap:8px;">
          <span>★ 11</span> 【3 分钟评委问答】官方 4 大考核维度 8 大攻防题深度攻防
        </h3>
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(460px, 1fr)); gap:12px;">
          
          <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(167,139,250,0.3); border-radius:8px; padding:12px;">
            <b style="color:#c4b5fd; font-size:13px;">Q1: 为什么用 AgentTeams 而非单 Agent + Prompt？</b>
            <p style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
              <b>靶向回答</b>：单 Agent 在物理世界无法做协议级权限硬隔离（L0 只读 vs L1/L2 写），且存在“自己干自己验收”自证漏洞。AgentTeams 实现了多 Worker 职责硬隔离与 Auditor 独立干净上下文重查客观事实。
            </p>
          </div>

          <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(167,139,250,0.3); border-radius:8px; padding:12px;">
            <b style="color:#c4b5fd; font-size:13px;">Q2: 怎么证明不是前端 Mock 而是真实可运行？</b>
            <p style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
              <b>靶向回答</b>：双重凭证：一是线上实机接口 `status.json`（广州云主机 Linux 真实容器集群、Matrix 协议、qwen3.8-max 真实端口心跳）；二是本地命令行 `uv run dianxun evaluate`，87 个测试用例全部确定性通过退出码 0。
            </p>
          </div>

          <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(167,139,250,0.3); border-radius:8px; padding:12px;">
            <b style="color:#c4b5fd; font-size:13px;">Q3: 大模型产生“幻觉”乱调工具乱花钱怎么办？</b>
            <p style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
              <b>靶向回答</b>：四道防御防线：① Policy 门禁强制挂起大额操作，触发店长移动端审批（HITL）；② 全量写强制携带 `idempotency_key` 幂等键防重试；③ Auditor 强制一票否决阻断；④ 数据库底层只增不可篡改审计。
            </p>
          </div>

          <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(167,139,250,0.3); border-radius:8px; padding:12px;">
            <b style="color:#c4b5fd; font-size:13px;">Q4: 除了便利店冷柜，还能拓展到什么领域？</b>
            <p style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
              <b>靶向回答</b>：凡是具备“设备恢复不等于资产安全”且“需要受控执行与独立稽核”的场景均可直接开箱复制：生物医药疫苗冷链（防失效疫苗出库）、中央厨房（防杂菌污染浓汤流入门店）、IDC 算力机房（防过温降频硬件受损）。Skill 标准契约解耦，迁移零成本。
            </p>
          </div>

        </div>
      </section>

      <!-- CHAPTER 12 -->
      <section id="d-ch12" style="background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px;">
        <h3 style="color:#38bdf8; font-size:16px; margin-top:0; display:flex; align-items:center; gap:8px;">
          <span>12</span> 答辩现场双屏配置、自检清单与应急预案
        </h3>
        <div style="font-size:12.5px; color:var(--text-secondary); line-height:1.7;">
          • <b>主屏幕（共享给评委）</b>：标签页 1 为 PPT 全屏演示 (`/zhuguang/ppt/`)，标签页 2 为指挥中心主页 (`/zhuguang/`)；<br>
          • <b>副屏幕（手机/平板提词）</b>：打开本网页 (`/zhuguang/defense.html`)，随时看掐秒台词；<br>
          • <b>备用网络</b>：如遇网络偶发波动，直接切换至备用镜像 `https://mazhi.icu/dianxun/`。
        </div>
      </section>

    </div>
"""

def update():
    # 1. Replace the iframe in build_delivery_portal.py with DOSSIER_HTML
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    
    # Locate section id="view-dossier"
    pattern = r'<section id="view-dossier" class="view-section">.*?</section>'
    new_section = f'<section id="view-dossier" class="view-section">\n{DOSSIER_HTML}\n  </section>'
    
    text = re.sub(pattern, new_section, text, flags=re.DOTALL)
    BUILD_SCRIPT.write_text(text, encoding="utf-8")
    print("Updated scripts/build_delivery_portal.py with native HTML dossier!")

    # 2. Generate standalone defense.html
    standalone_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>2026 GOAI 复赛答辩图文全景大纲 · 逐光队</title>
  <style>
    :root {{
      --bg: #070b14;
      --card: #0f172a;
      --border: rgba(56, 189, 248, 0.2);
      --border-subtle: rgba(255, 255, 255, 0.08);
      --text: #f8fafc;
      --text-secondary: #94a3b8;
      --text-muted: #64748b;
      --cyan: #38bdf8;
      --green: #10b981;
      --red: #ef4444;
      --font-mono: "Fira Code", monospace;
    }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", sans-serif;
      margin: 0;
      padding: 24px 16px;
      line-height: 1.6;
    }}
    .demo-btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      border: 1px solid var(--border);
      background: var(--card);
      color: var(--text);
      text-decoration: none;
      transition: all 0.2s ease;
    }}
    .demo-btn:hover {{
      background: #1e293b;
      border-color: var(--cyan);
    }}
    .tbl {{
      width: 100%;
      border-collapse: collapse;
    }}
    .tbl th, .tbl td {{
      border: 1px solid var(--border-subtle);
    }}
    a {{ color: var(--cyan); }}
  </style>
</head>
<body>
{DOSSIER_HTML}
</body>
</html>
"""
    STANDALONE_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    STANDALONE_HTML_PATH.write_text(standalone_html, encoding="utf-8")
    print(f"Generated standalone defense.html: {STANDALONE_HTML_PATH}")

if __name__ == "__main__":
    update()
