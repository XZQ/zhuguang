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
              📑 打开 12 页方案 PPT
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

      <!-- CHAPTER 9: 3-MIN SPEECH (HIGH IMPACT - 12 SLIDES STEP-BY-STEP) -->
      <section id="d-ch9" style="background: linear-gradient(180deg, rgba(234,179,8,0.12) 0%, rgba(15,23,42,0.95) 100%); border: 1.5px solid #eab308; border-radius:14px; padding:22px; margin-bottom:24px; box-shadow: 0 0 25px rgba(234,179,8,0.18);">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:16px;">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="background:#eab308; color:#0f172a; font-size:11px; font-weight:900; padding:2px 8px; border-radius:4px;">答辩必背核心</span>
              <h3 style="color:#fde047; font-size:19px; margin:0; font-weight:800;">
                ★ 09 【3 分钟项目陈述】12 页 PPT 逐页掐秒口播逐字稿（180 秒严格分秒版）
              </h3>
            </div>
            <p style="font-size:12.5px; color:#cbd5e1; margin-top:5px; margin-bottom:0;">
              全屏打开 <a href="./ppt/" target="_blank" style="color:#38bdf8; text-decoration:underline;">/zhuguang/ppt/</a>，右手按方向键 [→] 翻页，手机/副屏对照此稿口播，分秒不差！
            </p>
          </div>
          <span style="font-size:12px; font-weight:700; color:#fde047; background:rgba(0,0,0,0.5); padding:6px 12px; border-radius:6px; border:1px solid rgba(253,224,71,0.3); font-family:var(--font-mono);">
            总限时：180 秒（12 页，平均 15 秒/页）
          </span>
        </div>

        <div style="space-y: 12px; font-size: 13px; line-height: 1.8;">
          
          <!-- P01 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(56,189,248,0.25); border-left:4px solid #38bdf8; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#0284c7; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P01 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【封面】逐光 · 店巡 Agent 异常闭环基础设施</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 00:00 - 00:10 (10秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完“独立闭环”按 [→] 翻页</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “各位评委老师下午好！我们是第 13 队‘逐光’，今天汇报的作品是面向连锁门店的物理异常闭环基础设施——<b>店巡 Agent</b>。<br>
              在连锁冷链中，面对单柜失温等物理突发事件，我们的核心立意是：<b>先遏制风险，再诊断决策，最后基于客观证据实现独立闭环</b>。”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>画面焦点</b>：PPT 封面居中大标题与副标“先遏制风险，再诊断决策，最后验证闭环”。
            </div>
          </div>

          <!-- P02 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(234,179,8,0.25); border-left:4px solid #eab308; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#ca8a04; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P02 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【01·场景价值】总部运营要的不是告警，而是可安全放行的闭环</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 00:10 - 00:30 (20秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完“完整证据链”按 [→] 翻页</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “连锁门店缺的从来不是监控告警。传统系统每天数百条告警轰炸（例如某温盾系统 608 条警报），店长只能麻木点击‘标记已解决’，这是典型的假闭环！<br>
              更致命的是：<b>设备修好了、温度降回去了，不等于商品没变质！</b>误放行会导致严重食安事故，错关会导致追责断链。<br>
              总部运营要的从来不是通知推送，而是<b>能够证明‘可以安全放行’的完整证据链</b>。”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>画面焦点</b>：左侧三大痛点、中间 4 类输入、右侧 OUTPUT + DONE 安全放行完成条件。
            </div>
          </div>

          <!-- P03 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(56,189,248,0.25); border-left:4px solid #38bdf8; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#0284c7; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P03 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【02·系统架构】一个业务核心，两套可验证运行底座</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 00:30 - 00:48 (18秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完“动态协同”按 [→] 翻页</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “为此，逐光构筑了‘一个业务核心，两套运行底座’：<br>
              底层由 <b>IncidentService 状态机</b>提供全局唯一的单一事实源；<br>
              在本地端，采用 SQLite 和固定随机种子，保证评测 100% 确定性复现、零外部依赖；<br>
              在云端，无缝对接赛道指定的 <b>AgentTeams 平台与 PolarDB</b>，支撑 1 Manager + 5 Agent 生产级多 Worker 动态协同。”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>画面焦点</b>：中间黑色卡片 SINGLE SOURCE OF TRUTH，连接左右 SQLite 本地底座与 AgentTeams 云端底座。
            </div>
          </div>

          <!-- P04 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(16,185,129,0.25); border-left:4px solid #10b981; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#059669; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P04 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【03·五 Agent 职责】五个角色，不共享“宣布成功”的权力</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 00:48 - 01:06 (18秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完“独立稽核”按 [→] 翻页</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “在多 Agent 协同上，我们践行最小权限与职责分离原则，划分 5 个角色，<b>绝不共享‘宣布成功’的权力</b>：<br>
              • <b>Orchestrator</b> 仅调度协调，无领域写权；<br>
              • <b>Sentry</b> 只读巡检全网设备与时序去噪；<br>
              • <b>Diagnoser</b> 积分计算商品暴露风险与 Top-K 假设；<br>
              • <b>Executor</b> 受控执行 POS 停售锁与急修工单；<br>
              • <b>Auditor</b> 是核心守门员——<b>执行者绝不能自证成功</b>，必须由 Auditor 独立稽核！”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>画面焦点</b>：五列角色并排，特别强调最右侧 05 INDEPENDENT Auditor 的独立守卫地位。
            </div>
          </div>

          <!-- P05 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(56,189,248,0.25); border-left:4px solid #38bdf8; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#0284c7; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P05 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【04·五阶段闭环】从异常到关闭，每一步都有拒绝条件</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 01:06 - 01:22 (16秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完“沉淀知识复盘”按 [→] 翻页</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “业务状态机分为严密的五阶段，每一步都有严苛拒绝条件：<br>
              第一步‘发现与遏制’，首要动作不是报修，而是<b>立即在 POS 端下发停售锁保安全</b>；<br>
              随后完成诊断与审批，派工维修；<br>
              维修完成后进入第四步‘独立验证’，由 Auditor <b>核验温度恢复与商品批次双重事实</b>，才允许解除停售；最后沉淀知识复盘。”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>画面焦点</b>：横向 5 步流程卡片（01 DETECT → 02 DIAGNOSE → 03 EXECUTE → 04 VERIFY → 05 LEARN）。
            </div>
          </div>

          <!-- P06 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(239,68,68,0.25); border-left:4px solid #ef4444; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#b91c1c; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P06 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【05·六场景门禁】三条安全关闭，三条安全不关闭</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 01:22 - 01:40 (18秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完“绝不盲目关闭”按 [→] 翻页</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “在评测设计上，我们视<b>‘失败为一等公民’</b>，落地‘三条安全关闭，三条安全不关闭’：<br>
              场景 A 压缩机故障经双重验证后安全放行；场景 B 传感器误报通过 Westgard 质控降权与人工核验放行；<br>
              而场景 D 审批超时、场景 E 温度恢复但鲜奶变质、场景 F 接口 partial，系统坚决保持阻断与遏制状态，<b>宁可升级人工，绝不盲目关闭！</b>”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>画面焦点</b>：6 宫格卡片，对比上方绿色 CLOSED 与下方灰色 CONTAINED / BLOCKED 的鲜明反差。
            </div>
          </div>

          <!-- P07 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(56,189,248,0.25); border-left:4px solid #38bdf8; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#0284c7; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P07 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【06·Skill 工程】六个 P0 Skill 进入版本化 Registry 与 Worker ZIP</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 01:40 - 01:55 (15秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完“热插拔标准”按 [→] 翻页</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “在 Infra 规范性上，我们封装治理了 6 个核心 P0 Skill，全部具备 SemVer 语义化版本、输入输出 JSON Schema 强类型约束以及负向异常反例。<br>
              所有 Skill 已通过自动化流水线打包装入 Worker ZIP，通过了本地与平台静态契约校验，完全符合平台生产分发与热插拔标准。”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>画面焦点</b>：左侧 6 个版本化 Skill 条目与右侧 REGISTRY + PACKAGE 规范。
            </div>
          </div>

          <!-- P08 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(234,179,8,0.25); border-left:4px solid #eab308; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#ca8a04; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P08 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【07·MCP 与安全】先重查事实 再决定动作</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 01:55 - 02:10 (15秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完“永久拉黑”按 [→] 翻页</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “在工具集成上，我们实现了 15 个 MCP 工具，强制遵循<b>‘先重查事实，再决定动作’</b>。<br>
              系统设立四道安全闸：通过 Policy 拦截越权、写操作强加 Client-Token 幂等键、在 DB 底层剥夺审计修改权；<br>
              审批与人工证据录入仅开放给人类，而资金支付对所有 Agent 永久拉黑！”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>画面焦点</b>：左侧 5 P0 Queries 事实重查清单，右侧可逆、跨系统与不可逆操作分类与红线禁令。
            </div>
          </div>

          <!-- P09 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(16,185,129,0.25); border-left:4px solid #10b981; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#059669; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P09 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【08·评测证据】所有本地 P0 门禁通过，口径可追溯</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 02:10 - 02:26 (16秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完“架构的必要性”按 [→] 翻页</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “用数据说话：在本地评测门禁中，6 大场景 100% 确定性通过，产出 45 份哈希校验的 Evidence 证据包与 26 段完整 Trace，违规放行率为零！<br>
              消融实验更证实：<b>去掉 Auditor 独立稽核，将有 5 个失败场景被错误放行</b>，直接量化证明了多 Agent 架构的必要性！”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>画面焦点</b>：四大核心数字（6/6 场景、45/45 证据、26/26 Trace、0 违规），底部 Ablation 消融数据。
            </div>
          </div>

          <!-- P10 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(239,68,68,0.25); border-left:4px solid #ef4444; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#b91c1c; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P10 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【09·初赛反馈落地】反馈不写成口号，逐项落到可验证改造</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 02:26 - 02:40 (14秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完“环境兜底”按 [→] 翻页</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “初赛评委的每一条宝贵建议，我们都落地为了可运行的代码（如幻灯片红色列所示）：<br>
              我们将冷柜立为唯一主线做透闭环；通过 Auditor 证伪了单 Agent 自验缺陷；所有工程声明都有 87 个本地测试与 Docker 环境兜底，拒绝口号化。”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>画面焦点</b>：标红的整改列（聚焦主线、多 Agent 增益、复现证据）。
            </div>
          </div>

          <!-- P11 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(56,189,248,0.25); border-left:4px solid #38bdf8; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#0284c7; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P11 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【10·复制路径】复制的不是冷柜规则，而是“证据闭环控制面”</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 02:40 - 02:52 (12秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完“IDC 动环”按 [→] 翻页</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “逐光沉淀的不是冷柜的死规则，而是一套通用的‘证据闭环控制面’。<br>
              只要替换领域契约与工具，这套体系可直接复用到连锁餐饮中央厨房、工业设备预防性维护，乃至<b>生物医药疫苗冷链 (GSP) 与智算中心 IDC 动环</b>！”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>画面焦点</b>：左侧黑色沉淀控制面，右侧 PATH A 与 PATH B 迁移路径，底部拓展领域。
            </div>
          </div>

          <!-- P12 -->
          <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(167,139,250,0.25); border-left:4px solid #a78bfa; padding:12px 16px; border-radius:0 8px 8px 0;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#7c3aed; color:#fff; font-size:11px; font-weight:800; padding:2px 6px; border-radius:4px; font-family:var(--font-mono);">P12 / 12</span>
                <span style="color:#f8fafc; font-weight:700; font-size:13px;">【11·交付边界与总结】事件只有在证据闭环后才能关闭</span>
              </div>
              <div style="display:flex; gap:10px; font-size:11.5px; font-family:var(--font-mono);">
                <span style="color:#38bdf8; font-weight:700;">⏱ 02:52 - 03:00 (8秒)</span>
                <span style="color:#fde047; font-weight:700;">👉 念完致谢，投屏切至指挥中心</span>
              </div>
            </div>
            <div style="color:#f8fafc; background:rgba(0,0,0,0.3); padding:8px 12px; border-radius:6px; margin-bottom:6px;">
              “最后重申逐光的第一性原理：<b>‘温度恢复不等于商品安全，Agent 的完成声明绝不等于业务事实！’</b><br>
              逐光只做证据闭环。汇报完毕，感谢各位评委，请老师们批评指正！”
            </div>
            <div style="font-size:11.5px; color:#94a3b8;">
              👀 <b>动作配合</b>：致谢鞠躬，切到浏览器标签页 2（指挥中心 `https://mazhi.icu/zhuguang/`），准备随时现场点触演练。
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
    
    # Locate section id="view-dossier" all the way to <!-- Footer -->
    pattern = r'<section id="view-dossier" class="view-section">.*?(?=\s*<!-- Footer -->)'
    new_section = f'<section id="view-dossier" class="view-section">\n{DOSSIER_HTML}\n  </section>\n\n'
    
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
