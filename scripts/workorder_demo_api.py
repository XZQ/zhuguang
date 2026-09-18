#!/usr/bin/env python3
"""Backend API server for VeriAgent Work Order & Risk Control Playground.
Runs on mazhi-tencent (default port 18092), connects to SQLite runtime.db.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DEFAULT_DB = "/home/ubuntu/agentteams-competition/runtime/mcp-state/runtime.db"
LOCAL_FALLBACK_DB = str(Path(__file__).resolve().parent.parent / "demo" / "state" / "runtime.db")

def get_db_path() -> str:
    if os.path.exists(DEFAULT_DB):
        return DEFAULT_DB
    if os.path.exists(LOCAL_FALLBACK_DB):
        return LOCAL_FALLBACK_DB
    return DEFAULT_DB

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn

def now_iso() -> str:
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(tz).isoformat()

def sha256_str(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

class WorkOrderAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/")
        if path in {"", "/status", "/api/status", "/zhuguang/api/status"}:
            self._handle_status()
        elif path in {"/devices", "/api/devices", "/zhuguang/api/devices"}:
            self._handle_devices()
        else:
            self._send_json(404, {"ok": False, "error": f"Endpoint not found: {self.path}"})

    def do_POST(self) -> None:
        path = self.path.split("?")[0].rstrip("/")
        try:
            body = self._read_json_body()
        except Exception as e:
            self._send_json(400, {"ok": False, "error": f"Invalid JSON body: {str(e)}"})
            return

        try:
            if path in {"/workorders/create", "/api/workorders/create", "/zhuguang/api/workorders/create"}:
                self._handle_create_workorder(body)
            elif path in {"/approvals/decide", "/api/approvals/decide", "/zhuguang/api/approvals/decide"}:
                self._handle_decide_approval(body)
            elif path in {"/workorders/progress", "/api/workorders/progress", "/zhuguang/api/workorders/progress"}:
                self._handle_progress_workorder(body)
            elif path in {"/workorders/verify", "/api/workorders/verify", "/zhuguang/api/workorders/verify"}:
                self._handle_verify_workorder(body)
            elif path in {"/reset", "/api/reset", "/zhuguang/api/reset"}:
                self._handle_reset()
            else:
                self._send_json(404, {"ok": False, "error": f"Endpoint not found: {self.path}"})
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json(500, {"ok": False, "error": str(e)})

    def _handle_status(self) -> None:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM workorders")
            wo_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM approvals")
            app_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM devices")
            dev_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM audit_log")
            audit_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM incidents")
            inc_cnt = cur.fetchone()[0]

            cur.execute("SELECT * FROM workorders ORDER BY created_at DESC LIMIT 10")
            workorders = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM approvals ORDER BY created_at DESC LIMIT 5")
            approvals = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM devices")
            devices = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT audit_id, request_id, actor, tool_name, incident_id, created_at FROM audit_log ORDER BY created_at DESC LIMIT 6")
            audit_logs = [dict(r) for r in cur.fetchall()]

            self._send_json(200, {
                "ok": True,
                "db_path": get_db_path(),
                "timestamp": now_iso(),
                "counts": {
                    "workorders": wo_cnt,
                    "approvals": app_cnt,
                    "devices": dev_cnt,
                    "audit_log": audit_cnt,
                    "incidents": inc_cnt,
                },
                "workorders": workorders,
                "approvals": approvals,
                "devices": devices,
                "audit_logs": audit_logs,
            })
        finally:
            conn.close()

    def _handle_create_workorder(self, body: dict[str, Any]) -> None:
        store_id = body.get("store_id", "S03")
        device_id = body.get("device_id", "FROST-S03")
        fault = body.get("fault", "压缩机启动电容失效 / 停转")
        budget = float(body.get("budget", 420.0))
        assignee = body.get("assignee", "冷链特约维保中心 (Vendor A)")
        actor = body.get("actor", "Executor")
        simulate_risk = body.get("simulate_risk")
        approval_id = body.get("approval_id")

        now = now_iso()
        req_id = f"req_{uuid.uuid4().hex[:12]}"
        audit_id = f"aud_{uuid.uuid4().hex[:16]}"
        incident_id = body.get("incident_id", f"INC-20260918-{store_id}")
        action_id = f"act_{uuid.uuid4().hex[:8]}"

        conn = get_conn()
        try:
            # 1. Check RBAC Risk Condition
            if simulate_risk == "rbac_unauthorized" or actor not in ("Executor", "AuthenticatedClient"):
                err_msg = f"Actor {actor} is not authorized for create_workorder (Allowed: ['Executor'])"
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO audit_log (
                        audit_id, request_id, trace_id, tenant_id, actor, tool_name,
                        incident_id, action_id, policy_id, policy_version, policy_source_ref,
                        request_json, response_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    audit_id, req_id, f"tr_{uuid.uuid4().hex[:8]}", "demo", actor, "create_workorder",
                    incident_id, action_id, "coldchain-demo", "1.0.0", "project://config/policies/coldchain-demo.v1.json",
                    json.dumps(body, ensure_ascii=False),
                    json.dumps({"ok": False, "code": "FORBIDDEN", "error": err_msg}, ensure_ascii=False),
                    now
                ))
                conn.commit()
                self._send_json(403, {
                    "ok": False,
                    "code": "FORBIDDEN",
                    "actor": actor,
                    "error": err_msg,
                    "risk_type": "rbac_blocked",
                    "audit_id": audit_id,
                    "message": f"🛡️ [RBAC 刚性拦截] 角色 {actor} 无权调用 create_workorder，操作被底层网关立即熔断！"
                })
                return

            # 2. Check High Budget HITL Gate (threshold: 500.0)
            threshold = 500.0
            if (budget > threshold or simulate_risk == "hitl_exceed_budget") and not approval_id:
                new_app_id = f"app_hitl_{uuid.uuid4().hex[:8]}"
                deadline = (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))) + datetime.timedelta(minutes=5)).isoformat()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO approvals (
                        approval_id, incident_id, action_id, subject, status,
                        approvers_json, deadline, created_at, decided_at, decided_by, decision_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                """, (
                    new_app_id, incident_id, action_id, f"维修大额支出审批 (¥{budget})", "pending",
                    json.dumps(["store_manager"]), deadline, now
                ))
                # Record audit log
                cur.execute("""
                    INSERT INTO audit_log (
                        audit_id, request_id, trace_id, tenant_id, actor, tool_name,
                        incident_id, action_id, policy_id, policy_version, policy_source_ref,
                        request_json, response_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    audit_id, req_id, f"tr_{uuid.uuid4().hex[:8]}", "demo", actor, "create_workorder",
                    incident_id, action_id, "coldchain-demo", "1.0.0", "project://config/policies/coldchain-demo.v1.json",
                    json.dumps(body, ensure_ascii=False),
                    json.dumps({"ok": False, "approval_required": True, "approval_id": new_app_id}, ensure_ascii=False),
                    now
                ))
                conn.commit()

                self._send_json(200, {
                    "ok": False,
                    "policy_blocked": True,
                    "code": "APPROVAL_REQUIRED",
                    "risk_type": "hitl_threshold_exceeded",
                    "approval_id": new_app_id,
                    "budget": budget,
                    "threshold": threshold,
                    "incident_id": incident_id,
                    "action_id": action_id,
                    "audit_id": audit_id,
                    "message": f"⚠️ [HITL 刚性门禁] 预算 ¥{budget} 超过门店授权门禁 ¥{threshold}！系统刚性拦截直接下发，已挂起并生成店长审批单：{new_app_id}"
                })
                return

            # 3. Normal / Approved Flow: Commit to workorders table
            cur = conn.cursor()
            # Ensure incident row exists
            cur.execute("""
                INSERT OR IGNORE INTO incidents (
                    incident_id, trace_id, tenant_id, store_id, phase, incident_status,
                    work_status, case_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                incident_id, f"tr_{uuid.uuid4().hex[:8]}", "demo", store_id, "execution",
                "in_progress", "repair_dispatched", json.dumps({"fault": fault, "device_id": device_id}, ensure_ascii=False),
                now
            ))

            wid = f"wo_{int(datetime.datetime.now().timestamp())}_{uuid.uuid4().hex[:4]}"
            cur.execute("""
                INSERT INTO workorders (
                    workorder_id, incident_id, action_id, store_id, device_id,
                    fault, budget, status, assignee, completion_evidence_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                wid, incident_id, action_id, store_id, device_id,
                fault, budget, "assigned", assignee, json.dumps({}),
                now, now
            ))

            audit_hash = sha256_str(f"{wid}:{budget}:{store_id}:{device_id}:{now}")
            cur.execute("""
                INSERT INTO audit_log (
                    audit_id, request_id, trace_id, tenant_id, actor, tool_name,
                    incident_id, action_id, policy_id, policy_version, policy_source_ref,
                    request_json, response_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                audit_id, req_id, f"tr_{uuid.uuid4().hex[:8]}", "demo", actor, "create_workorder",
                incident_id, action_id, "coldchain-demo", "1.0.0", "project://config/policies/coldchain-demo.v1.json",
                json.dumps(body, ensure_ascii=False),
                json.dumps({"ok": True, "workorder_id": wid, "audit_hash": audit_hash}, ensure_ascii=False),
                now
            ))
            conn.commit()

            self._send_json(200, {
                "ok": True,
                "workorder": {
                    "workorder_id": wid,
                    "incident_id": incident_id,
                    "action_id": action_id,
                    "store_id": store_id,
                    "device_id": device_id,
                    "fault": fault,
                    "budget": budget,
                    "status": "assigned",
                    "assignee": assignee,
                    "approval_id": approval_id,
                    "created_at": now,
                    "audit_hash": audit_hash,
                },
                "message": f"✅ 工单已生成并成功写入底层 SQLite 数据库！工单号: {wid} · 状态: 已派单 (assigned)"
            })
        finally:
            conn.close()

    def _handle_decide_approval(self, body: dict[str, Any]) -> None:
        approval_id = body.get("approval_id")
        decision = body.get("decision", "approved")  # approved, rejected, timeout
        reason = body.get("reason", "店长决策")
        decided_by = body.get("decided_by", "store_manager")
        now = now_iso()

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE approvals
                SET status = ?, decided_at = ?, decided_by = ?, decision_reason = ?
                WHERE approval_id = ?
            """, (decision, now, decided_by, reason, approval_id))

            # Audit record
            audit_id = f"aud_{uuid.uuid4().hex[:16]}"
            req_id = f"req_{uuid.uuid4().hex[:12]}"
            cur.execute("""
                INSERT INTO audit_log (
                    audit_id, request_id, trace_id, tenant_id, actor, tool_name,
                    incident_id, action_id, policy_id, policy_version, policy_source_ref,
                    request_json, response_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                audit_id, req_id, f"tr_{uuid.uuid4().hex[:8]}", "demo", "StoreManager", "decide_approval",
                body.get("incident_id", "INC-20260918-S03"), body.get("action_id", "act_hitl"),
                "coldchain-demo", "1.0.0", "project://config/policies/coldchain-demo.v1.json",
                json.dumps(body, ensure_ascii=False),
                json.dumps({"ok": True, "decision": decision}, ensure_ascii=False),
                now
            ))

            if decision == "approved":
                # Create the approved workorder
                wid = f"wo_hitl_{int(datetime.datetime.now().timestamp())}_{uuid.uuid4().hex[:4]}"
                store_id = body.get("store_id", "S03")
                device_id = body.get("device_id", "FROST-S03")
                fault = body.get("fault", "压缩机总成更换 (店长审批通过)")
                budget = float(body.get("budget", 850.0))
                assignee = body.get("assignee", "冷链特约维保中心 (Vendor A)")
                incident_id = body.get("incident_id", f"INC-20260918-{store_id}")
                action_id = body.get("action_id", f"act_{uuid.uuid4().hex[:8]}")

                cur.execute("""
                    INSERT INTO workorders (
                        workorder_id, incident_id, action_id, store_id, device_id,
                        fault, budget, status, assignee, completion_evidence_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    wid, incident_id, action_id, store_id, device_id,
                    fault, budget, "assigned", assignee, json.dumps({"approval_id": approval_id}),
                    now, now
                ))
                conn.commit()
                self._send_json(200, {
                    "ok": True,
                    "decision": "approved",
                    "approval_id": approval_id,
                    "workorder": {
                        "workorder_id": wid,
                        "incident_id": incident_id,
                        "budget": budget,
                        "status": "assigned",
                        "assignee": assignee,
                        "created_at": now,
                    },
                    "message": f"✅ 店长已确认批准！大额工单 {wid} (¥{budget}) 已合规写入底层数据库并派发施工！"
                })
            else:
                # Rejected or Timeout -> 0 rows written!
                conn.commit()
                self._send_json(200, {
                    "ok": True,
                    "decision": decision,
                    "approval_id": approval_id,
                    "workorder": None,
                    "message": f"🚫 [风控刚性阻断生效] 审批状态: {decision} ({reason})！系统严守红线，底层工单表保持 0 写入，超额支出已被完全遏制！"
                })
        finally:
            conn.close()

    def _handle_progress_workorder(self, body: dict[str, Any]) -> None:
        wid = body.get("workorder_id")
        next_status = body.get("status", "in_progress")  # in_progress, pending_verification
        evidence = body.get("evidence", {})
        now = now_iso()

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE workorders
                SET status = ?, completion_evidence_json = ?, updated_at = ?
                WHERE workorder_id = ?
            """, (next_status, json.dumps(evidence, ensure_ascii=False), now, wid))
            conn.commit()
            self._send_json(200, {
                "ok": True,
                "workorder_id": wid,
                "status": next_status,
                "message": f"工单 {wid} 状态已更新为: {next_status}"
            })
        finally:
            conn.close()

    def _handle_verify_workorder(self, body: dict[str, Any]) -> None:
        wid = body.get("workorder_id")
        condition = body.get("condition", "normal")  # normal or anti_self_verify_spoiled
        device_temp = float(body.get("device_temp", 4.2))
        exposure_minutes = int(body.get("exposure_minutes", 22 if condition == "normal" else 48))
        now = now_iso()
        audit_id = f"aud_{uuid.uuid4().hex[:16]}"
        req_id = f"req_{uuid.uuid4().hex[:12]}"

        conn = get_conn()
        try:
            cur = conn.cursor()
            if condition == "normal":
                # Both physical and data gates pass!
                cur.execute("""
                    UPDATE workorders
                    SET status = 'closed', updated_at = ?
                    WHERE workorder_id = ?
                """, (now, wid))
                # Release sales hold
                cur.execute("""
                    UPDATE sales_holds
                    SET status = 'released', released_at = ?
                    WHERE store_id = 'S03'
                """, (now,))
                # Write Auditor verification audit
                cur.execute("""
                    INSERT INTO audit_log (
                        audit_id, request_id, trace_id, tenant_id, actor, tool_name,
                        incident_id, action_id, policy_id, policy_version, policy_source_ref,
                        request_json, response_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    audit_id, req_id, f"tr_{uuid.uuid4().hex[:8]}", "demo", "Auditor", "verify_recovery",
                    "INC-20260918-S03", "act_verify", "coldchain-demo", "1.0.0", "project://config/policies/coldchain-demo.v1.json",
                    json.dumps(body, ensure_ascii=False),
                    json.dumps({"result": "PASS", "device_temp": device_temp, "exposure_minutes": exposure_minutes}, ensure_ascii=False),
                    now
                ))
                conn.commit()
                self._send_json(200, {
                    "ok": True,
                    "verification": "PASS",
                    "device_temp": device_temp,
                    "exposure_minutes": exposure_minutes,
                    "status": "closed",
                    "sales_hold": "released",
                    "message": f"🛡️ [Auditor 双门独立验真通过] 物理温度恢复至 {device_temp}°C，累计暴露积温时间 {exposure_minutes}分钟 (<30m限额)。POS 解除停售，工单合规关闭！"
                })
            else:
                # Anti-self-verification triggers!
                cur.execute("""
                    UPDATE workorders
                    SET status = 'vetoed_food_unsafe', updated_at = ?
                    WHERE workorder_id = ?
                """, (now, wid))
                # Mark inventory batch as disposed
                cur.execute("""
                    UPDATE inventory_batches
                    SET disposition = 'disposed', safe_for_sale = 0, updated_at = ?
                    WHERE store_id = 'S03' AND device_id = 'FROST-S03'
                """, (now,))
                # Write Auditor veto audit
                cur.execute("""
                    INSERT INTO audit_log (
                        audit_id, request_id, trace_id, tenant_id, actor, tool_name,
                        incident_id, action_id, policy_id, policy_version, policy_source_ref,
                        request_json, response_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    audit_id, req_id, f"tr_{uuid.uuid4().hex[:8]}", "demo", "Auditor", "verify_recovery",
                    "INC-20260918-S03", "act_verify", "coldchain-demo", "1.0.0", "project://config/policies/coldchain-demo.v1.json",
                    json.dumps(body, ensure_ascii=False),
                    json.dumps({"result": "VETO", "veto_reason": "Thermodynamic milk exposure 48 min exceeds threshold"}, ensure_ascii=False),
                    now
                ))
                conn.commit()
                self._send_json(200, {
                    "ok": False,
                    "verification": "VETO",
                    "veto_reason": f"冷柜虽降至 {device_temp}°C，但热力积分证明巴氏鲜奶超温暴露达 {exposure_minutes} 分钟 (>30m安全红线)，已发生不可逆酸败！",
                    "device_temp": device_temp,
                    "exposure_minutes": exposure_minutes,
                    "status": "vetoed_food_unsafe",
                    "sales_hold": "PERMANENT_LOCKED",
                    "batch_disposition": "disposed",
                    "message": f"🚨 [物理反自验一票否决] 师傅完工申请被 Auditor 独立否决！严禁解除 POS 销售锁，巴氏鲜奶批次强制标记为报废 (disposed)，防止有毒变质食品流出！"
                })
        finally:
            conn.close()

    def _handle_reset(self) -> None:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM workorders")
            cur.execute("DELETE FROM approvals")
            cur.execute("DELETE FROM incidents WHERE incident_id LIKE '%20260918%'")
            cur.execute("DELETE FROM audit_log WHERE tool_name IN ('create_workorder', 'decide_approval', 'verify_recovery')")
            # reset batch state
            cur.execute("UPDATE inventory_batches SET disposition = 'unknown', safe_for_sale = 0 WHERE store_id = 'S03'")
            conn.commit()
            self._send_json(200, {
                "ok": True,
                "message": "已重置演示数据，workorders 与 approvals 表已恢复干净初始状态！"
            })
        finally:
            conn.close()

def run_server(port: int = 18092) -> None:
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, WorkOrderAPIHandler)
    print(f"🚀 WorkOrder Demo API Server running at http://127.0.0.1:{port}/ using DB: {get_db_path()}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18092
    run_server(port)
