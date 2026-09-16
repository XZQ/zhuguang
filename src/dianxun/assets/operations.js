"use strict";
let bearer = "", cursor = null, selected = null, epoch = 0;
const byId = id => document.getElementById(id);
const node = (tag, text, cls) => { const el = document.createElement(tag); if (text != null) el.textContent = text; if (cls) el.className = cls; return el; };
const pretty = value => JSON.stringify(value, null, 2);
const decoded = row => Object.fromEntries(Object.entries(row).map(([key,value]) => {
  if (key.endsWith("_json") && typeof value === "string") { try { value = JSON.parse(value); } catch { /* Preserve original text. */ } }
  return [key.replace(/_json$/, ""), value];
}));
function status(text, error=false) { byId("status").textContent = text; byId("status").className = error ? "error" : "muted"; }
async function rpc(name, args) {
  const response = await fetch("/runtime", {method:"POST", cache:"no-store", credentials:"omit",
    headers:{"Content-Type":"application/json", Authorization:`Bearer ${bearer}`},
    body:JSON.stringify({jsonrpc:"2.0", id:1, method:"tools/call", params:{name, arguments:args}})});
  if (!response.ok) throw new Error(`请求失败（HTTP ${response.status}）`);
  const envelope = await response.json();
  if (envelope.error || !envelope.result?.content?.[0]?.text) throw new Error("响应格式无效");
  const result = JSON.parse(envelope.result.content[0].text);
  if (envelope.result.isError) throw new Error(result.error?.message || "无权读取或服务暂不可用");
  return result;
}
function table(title, rows, columns) {
  const section = node("section", null, "panel"); section.append(node("h2", title));
  if (!rows?.length) { section.append(node("p", "尚无记录", "muted")); return section; }
  const wrapper = node("div", null, "scroll"), t = node("table"), head = node("tr");
  for (const [,label] of columns) head.append(node("th",label));
  const thead = node("thead"); thead.append(head); t.append(thead);
  const tbody = node("tbody");
  for (const item of rows) { const tr = node("tr"); for (const [key] of columns) {
    const value = item[key]; tr.append(node("td", typeof value === "object" ? pretty(value) : String(value ?? "—")));
  } tbody.append(tr); }
  t.append(tbody); wrapper.append(t); section.append(wrapper); return section;
}
function details(title, value) { const el=node("details"), summary=node("summary",title); el.append(summary,node("pre",pretty(value))); return el; }
function render(data) {
  const root=byId("casefile"); root.replaceChildren(); root.hidden=false;
  const c=data.incident, ctx=data.context || {}, r=data.records;
  const header=node("section",null,"panel"); header.append(node("h2",c.incident_id));
  header.append(node("p",`${c.incident_status} · ${c.phase} · ${c.work_status}`));
  const scope=data.scope || {version:c.scope_version || 0,state:c.scope_state || "legacy_unversioned",snapshot:c.scope_snapshot,digest:c.scope_digest};
  header.append(node("p",`范围版本 ${scope.version} · ${scope.state} · 恢复轮次 ${ctx.recovery?.generation || 0}`));
  if(scope.state === "requires_reconciliation") header.append(node("p","当前库存范围待 Human 来源核对，不代表已经获得处置或放行授权。","error"));
  header.append(details("当前范围快照与摘要",{snapshot:scope.snapshot,digest:scope.digest}));
  header.append(node("p",`后端 ${data.backend} · 构建 ${data.build_revision} · 来源 ${data.data_origin === "scenario" ? "模拟场景" : "尚未核验"}`));
  header.append(node("p",`采集时间 ${data.captured_at} · 业务时间 ${data.business_time} · 证据时钟 ${data.evidence_clock === "virtual_demo" ? "虚拟演示" : "真实时间"} · Trace ${data.trace.status}`,"muted"));
  if (data.truncated.length) header.append(node("p",`显示已截断：${data.truncated.join("、")}。完整取证请使用封存工具。`,"error"));
  const refresh=node("button","刷新当前事件"); refresh.onclick=()=>loadCase(c.incident_id); header.append(refresh);
  header.append(node("p","设备恢复和商品放行分别判断。平台关联由 Worker 提交，需核对原始日志。", "muted")); root.append(header);
  const grid=node("div",null,"grid");
  grid.append(table("设备状态",r.devices,[["device_id","设备"],["health_state","状态"],["compressor_state","压缩机"]]));
  grid.append(table("商品与销售限制",r.inventory_batches.map(b=>({...b,hold:r.sales_holds.some(h=>h.batch_id===b.batch_id&&h.status==="active")?"限制中":"无本事件活动限制"})),[["batch_id","批次"],["disposition","处置"],["safe_for_sale","销售安全标记"],["hold","限制"]])); root.append(grid);
  root.append(table("独立复核",r.verifications.map(decoded),[["subject","对象"],["result","结果"],["verifier","复核角色"],["verified_at","时间"]]));
  root.append(table("范围修订与来源",(r.scope_revisions || []).map(decoded),[["scope_version","版本"],["change_id","变更编号"],["actor","操作者"],["source_ref","来源引用"],["before","原范围"],["after","新范围"]]));
  root.append(node("p","可能包含其他事件涉及的拆批；本事件归属以范围修订中的变更编号为准"));
  root.append(table("关联批次共享谱系",r.batch_lineage || [],[["parent_batch_id","父批次"],["parent_quantity","拆分前数量"],["child_batch_id","子批次"],["child_quantity","分配数量"],["change_id","变更编号"]]));
  root.append(table("审批决定与当前适用性",scope.approval_applicability || [],[["approval_id","批准编号"],["action_id","动作"],["decision","历史决定"],["applicability","当前适用性"],["scope_version","申请范围版本"],["deadline","有效期"]]));
  root.append(node("p","批准、外部回执与恢复轮次分别保留；历史批准不自动覆盖新增或拆分对象，生成遏制待办也不代表外部渠道已经停售。","muted"));
  root.append(table("Worker 任务与租约",ctx.assignments,[["phase","阶段"],["worker","责任 Worker"],["assignment_id","接单编号"],["status","状态"],["attempt","次数"],["lease_expires_at","租约截止"]]));
  root.append(table("平台任务与房间消息",ctx.platform_links,[["stage","阶段"],["worker_id","提交 Worker"],["task_id","AT 任务"],["room_id","房间"],["message_id","消息"],["verification","核验状态"]]));
  for (const [title,value] of [["原始事件",ctx.source_events || []],["每次执行与复核输出",ctx.attempt_outputs || []],["中断、重试与恢复",ctx.recovery || {}],["审批记录",r.approvals.map(decoded)],["动作及回执",r.actions.map(decoded)],["实物凭证",r.manual_evidence.map(decoded)],["温度记录",r.device_readings],["逐条业务审计",r.audit_log.map(decoded)],["逐条 Trace 与实际 Skill 版本",data.trace.rows.map(decoded)],["当前规则与 Skill 注册表（历史版本见审计和 Trace）",{policy:data.current_policy,registry:data.current_skill_registry}],["完整档案",data]]) {
    const panel=node("section",null,"panel"); panel.append(details(title,value)); root.append(panel);
  }
}
async function loadCase(id) { const version=epoch; selected=id; status("正在读取事件档案…"); try {
  const data=await rpc("runtime_casefile",{incident_id:id}); if(version!==epoch || selected!==id)return;
  render(data); status("已读取；页面只提供查询。");
} catch(error) { if(version===epoch)status(error.message,true); } }
async function listMore() { const version=epoch; try {
  const data=await rpc("runtime_cases",{after:cursor || "",limit:50}); if(version!==epoch)return;
  for(const item of data.items) {const button=node("button",`${item.incident_id} · ${item.incident_status}`);button.onclick=()=>loadCase(item.incident_id);byId("cases").append(button);}
  cursor=data.next_cursor;byId("more").hidden=!cursor;status(data.items.length?"选择事件查看档案":"当前身份范围内没有事件");
}catch(error){if(version===epoch)status(error.message,true);} }
function clear() {epoch++;bearer="";cursor=null;selected=null;byId("token").value="";byId("cases").replaceChildren();byId("casefile").replaceChildren();byId("casefile").hidden=true;byId("more").hidden=true;status("已清空凭证与事件内容");}
byId("connect").onsubmit=event=>{event.preventDefault();const token=byId("token").value.trim();clear();bearer=token;listMore();};
byId("disconnect").onclick=clear;byId("more").onclick=listMore;
