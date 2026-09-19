---
title: 店巡｜面向物理实体流程的可验证多智能体运行时
emoji: 🏪
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.29.0
app_file: app.py
pinned: false
---

# 🏪 店巡｜面向物理实体流程的可验证多智能体运行时

> **世界人工智能开源大赛 (GOAI 2026) 决赛参赛作品**  
> **作品名称**：店巡  
> **参赛队名**：逐光  
> **赛道分类**：Agent Infra（智能体基础设施）  
> **GitHub 开源仓库**：[marongwork/zhuguang](https://github.com/marongwork/zhuguang)  
> **生产线上端点**：[https://sh.mazhi.icu/zhuguang/](https://sh.mazhi.icu/zhuguang/)  

---

## 📌 项目定位与价值主张

物理实体流程与纯数字大模型交互存在着不可逾越的鸿沟：**硬件恢复不等于资产安全，执行者声明完成不等于业务真正完成**。

**「店巡」** 是专为物理实体流程（以连锁零售高敏冷链为第一基准矩阵，并泛化至生物医药冷库、智算机房液冷）打造的**可验证多智能体运行时架构**。通过确立三大不可逆公理与反自验执行闭环，彻底解决物理-数字协同中的执行失控、自证幻觉与资产裸奔风险。

---

## 💡 物理实体流程的三大不可逆公理

| 公理 | 核心论断 | 传统系统致命盲区 | 店巡范式质变 |
| :--- | :--- | :--- | :--- |
| **公理一：状态不对称** | 硬件恢复 ≠ 承载资产安全 | 传统工单以为温度降下来就万事大吉，放任变质商品流向货架酿成灾难 | 结合 **Arrhenius 微生物动力学积分**，动态定损商品，3 折甩卖挽损或不可逆销毁 |
| **公理二：执行不可逆** | 物理动作无“代码假撤销” | 软件报错可随时 rollback，但物理世界上门拆机、丢弃货物产生真实法律责任 | **五层工程安全门禁 + 幂等 Token + 人类审批 (HITL)**，杜绝非受控副作用 |
| **公理三：反自验闭环** | 执行者绝无权自证成功 | 大模型执行者“自己做事自己验收”，必然出现自证幻觉（False Pass） | **反自验（Anti-Self-Verification）架构**：Auditor 独立带外重查传感器预言机，方可终结事件 |

---

## 🏗️ 架构栈与多智能体分工矩阵

系统采用 **“通用核心引擎 (Kernel) + 领域无侵入配置插件 (Domain Profiles)”** 的高度解耦架构：

```
┌────────────────────────────────────────────────────────┐
│ TOP: 跨行业领域配置插件 (Domain Profiles - 0% 硬编码)  │
│  • Profile 01: 零售高敏冷链 (Arrhenius 动力学 / POS 熔断)│
│  • Profile 02: 医药疫苗温控 (GSP 刚性监管 / 批次双盲验真)│
│  • Profile 03: 智算机房 HPC (GPU 功耗墙 / 算力热迁移)   │
├────────────────────────────────────────────────────────┤
│ MIDDLE: 店巡通用核心引擎 (Dianxun Verifiable Kernel)   │
│  • Orchestrator: 确定性非阻塞状态机编排                │
│  • Sentry      : 流式时序去噪与 Westgard 质控哨兵      │
│  • Diagnoser   : 因果 Top-K 退化动力学推断引擎         │
│  • Executor    : 受控物理/数字执行与异步悬挂           │
│  • Auditor     : 隔离上下文带外独立验真预言机          │
│  • AgentLoop   : 全量 Trace 回流与自演进评估流         │
├────────────────────────────────────────────────────────┤
│ BOTTOM: 物理-数字双域适配器与预言机 (Adapters)         │
│  • IoT 时序传感网  • 工业 PLC 梯形图  • POS/ERP 业务中台│
│  • Matrix/Element 去中心化通信网关  • 人工工单 Human Tool │
└────────────────────────────────────────────────────────┘
```

---

## 🌐 全国 300 家门店 · 1,500 台设备生产/高保真仿真大盘

- **全国大盘看板**：[https://sh.mazhi.icu/zhuguang/phx-fleet.html](https://sh.mazhi.icu/zhuguang/phx-fleet.html)
- **覆盖规模**：上海、北京、广州、深圳、杭州、成都等 **12 座核心城市、300 家门店、1,500 台多温区冷柜设备**。
- **数据深度**：**5,100 批次商品动态追踪、156 项历史异常事件全链路归档**，支持毫秒级时序 SVG 曲线回溯与交互式下钻。

---

## 🚀 线上可交互体验链接

- 🏪 **全国 300 店态势大盘**：[https://sh.mazhi.icu/zhuguang/phx-fleet.html](https://sh.mazhi.icu/zhuguang/phx-fleet.html)
- ⚡ **店巡交互主门户**：[https://sh.mazhi.icu/zhuguang/](https://sh.mazhi.icu/zhuguang/)
- 📊 **决赛技术答辩与第一性原理深度解析**：[https://sh.mazhi.icu/zhuguang/defense.html](https://sh.mazhi.icu/zhuguang/defense.html)
- 📑 **12 页决赛演示幻灯 (Slide Deck)**：[https://sh.mazhi.icu/zhuguang/ppt/index.html](https://sh.mazhi.icu/zhuguang/ppt/index.html)
- 💬 **Element 实机团队协作群**：[进入 Matrix 实机群](https://sh.mazhi.icu/zhuguang/chat/#/room/!1Trrg2QNy3LDEFqoVk:matrix-local.agentteams.io:28080)
