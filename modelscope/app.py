"""
GOAI 2026 决赛参赛作品：店巡 (VeriPatrol) (逐光团队)
ModelScope 创空间展示应用
"""
import gradio as gr

CUSTOM_CSS = """
.container {
    max-width: 100% !important;
    padding: 0 !important;
}
iframe {
    width: 100%;
    min-height: 860px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    background: #0b0f17;
}
"""

MARKDOWN_OVERVIEW = """
# 🏪 店巡 (VeriPatrol)｜面向物理实体流程的可验证多智能体运行时
> **世界人工智能开源大赛 (GOAI 2026) 决赛参赛作品**  
> **参赛队名**：逐光 ｜ **作品名称**：店巡 (VeriPatrol) ｜ **赛道**：Agent Infra (智能体基础设施)  
> **开源代码仓库**：[GitHub - marongwork/zhuguang](https://github.com/marongwork/zhuguang)  
> **线上生产端点**：[https://sh.mazhi.icu/zhuguang/](https://sh.mazhi.icu/zhuguang/)

---

### 💡 核心第一性原理：物理世界的三大不可逆公理
1. **公理一：状态不对称** —— 硬件恢复 ≠ 承载资产安全（冷柜降温不等于鲜奶未变质）。
2. **公理二：执行不可逆** —— 物理动作无“代码假撤销”（上门拆机、商品销毁具法律与经济事实）。
3. **公理三：反自验闭环** —— 执行者绝无权自证成功（严防 LLM 自查幻觉，Auditor 独立带外重查传感器预言机）。

### 🌐 生产与高保真仿真规模矩阵
- **业务场景**：连锁便利零售高敏冷链（并实证生物医药冷库、智算机房液冷两大泛化基准）。
- **仿真与压测**：**300 家门店 · 1,500 台多温区冷柜设备 · 5,100 批次商品 · 156 项历史异常事件**。
- **五大多智能体角色协同**：Sentry (流式哨兵) ➔ Diagnoser (动力学根因诊断) ➔ Executor (双域受控执行) ➔ Auditor (独立带外核验) ➔ Orchestrator (状态机编排)。
"""

def create_demo():
    with gr.Blocks(title="店巡 (VeriPatrol)｜面向物理实体流程的可验证多智能体运行时 (逐光团队)", css=CUSTOM_CSS, theme=gr.themes.Default(primary_hue="blue", neutral_hue="slate")) as demo:
        gr.Markdown(MARKDOWN_OVERVIEW)
        
        with gr.Tabs():
            with gr.TabItem("🏪 全国 300 店实盘/仿真大盘 (PHX Fleet)"):
                gr.Markdown("展示覆盖 12 座核心城市、300 家门店、1,500 台设备的实时巡检、温度时序曲线与异常事件列表：")
                gr.HTML('<iframe src="https://sh.mazhi.icu/zhuguang/phx-fleet.html" allow="fullscreen"></iframe>')
                
            with gr.TabItem("⚡ 店巡交互主门户 (Main Portal)"):
                gr.Markdown("包含全景监控、五大 Agent 实时事件状态机、Element 团队群联动演示：")
                gr.HTML('<iframe src="https://sh.mazhi.icu/zhuguang/" allow="fullscreen"></iframe>')
                
            with gr.TabItem("📊 决赛技术答辩与 Q&A (Defense Matrix)"):
                gr.Markdown("包含 14 大核心答辩题、反击口播要点、五层工程验证与资产救回全景对比：")
                gr.HTML('<iframe src="https://sh.mazhi.icu/zhuguang/defense.html" allow="fullscreen"></iframe>')

            with gr.TabItem("📑 12 页决赛演示幻灯 (Finals Slide Deck)"):
                gr.Markdown("面向评委的第一性原理推导、架构栈三层解耦与压测证据展示：")
                gr.HTML('<iframe src="https://sh.mazhi.icu/zhuguang/ppt/index.html" allow="fullscreen"></iframe>')

    return demo

if __name__ == "__main__":
    demo = create_demo()
    demo.launch(server_name="0.0.0.0", server_port=7860)
