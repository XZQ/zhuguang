"""改造前 MCP Server：暴露 16 个静态 CSV / 内存函数。

该入口保留旧 Demo 兼容性，不代表复赛 P0 的 12 个有状态函数已经完成。
M1 会替换注册表并保持 Streamable HTTP / JSON-RPC 2.0 协议入口。

满足赛题 2.2:外部工具和系统接入协议。
设计:
- 用 Python 标准库 http.server 实现,无第三方依赖(评审可离线跑)
- 实现 MCP 核心方法:initialize / tools/list / tools/call
- 鉴权:Bearer token(环境变量 MCP_TOKEN;空=开发模式跳过)
- AgentTeams 集成:经 Higress AI 网关授权,Worker 用 mcpServers 字段配置此地址

启动:
    python3 -m dianxun.mcp.server                       # 默认 0.0.0.0:8080
    MCP_TOKEN=xxx PORT=9000 python3 -m dianxun.mcp.server

测试:
    curl -X POST http://127.0.0.1:8080 -H 'Content-Type: application/json' \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
"""

from __future__ import annotations
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from . import (pos, wms, iot, price, im, approval, workorder)

# ===== 工具注册表:工具名 -> (函数, 描述, 入参 schema) =====
# 契约对齐 05-MCP工具契约.md
TOOLS: dict[str, dict] = {
    # --- 读类 ---
    "query_sales": {"fn": pos.query_sales, "desc": "查询销售流水(window/store_ids/sku_ids)",
                    "schema": {"window": "object", "store_ids": "array?", "sku_ids": "array?"}},
    "query_realtime_sales": {"fn": pos.query_realtime_sales, "desc": "查某店近1h实时销售",
                             "schema": {"store_id": "string"}},
    "query_stock": {"fn": wms.query_stock, "desc": "查询门店库存",
                    "schema": {"store_id": "string", "sku_ids": "array?"}},
    "query_expiry": {"fn": wms.query_expiry, "desc": "查询临期商品",
                     "schema": {"store_id": "string", "within_days": "number?"}},
    "list_devices": {"fn": iot.list_devices, "desc": "列出门店冷柜设备",
                     "schema": {"store_id": "string"}},
    "query_device_series": {"fn": iot.query_device_series, "desc": "查询设备温度时序",
                            "schema": {"device_id": "string", "window_hours": "number?"}},
    "query_price": {"fn": price.query_price, "desc": "查询三方价格(系统/价签/收银)",
                    "schema": {"store_id": "string", "sku_ids": "array?"}},
    # --- 写类(需审批/幂等) ---
    "apply_price_change": {"fn": price.apply_price_change,
                           "desc": "批量改价(审批后;幂等key;>20SKU需approval_ticket)",
                           "schema": {"store_id": "string", "items": "array",
                                      "idempotency_key": "string", "approval_ticket": "string?"}},
    "revert_price_change": {"fn": price.revert_price_change, "desc": "回滚改价",
                            "schema": {"change_id": "string"}},
    # --- 通知/审批/工单 ---
    "send_notice": {"fn": im.send_notice, "desc": "发送IM通知",
                    "schema": {"channel": "string", "template_id": "string", "payload": "object"}},
    "send_approval_request": {"fn": im.send_approval_request, "desc": "发送审批请求",
                              "schema": {"channel": "string", "title": "string", "content": "string"}},
    "create_approval": {"fn": approval.create_approval, "desc": "创建审批单",
                        "schema": {"subject": "string", "type": "string", "payload": "object",
                                   "approvers": "array", "timeout_min": "number?"}},
    "check_approval_status": {"fn": approval.check_status, "desc": "查询审批状态",
                              "schema": {"approval_id": "string"}},
    "create_workorder": {"fn": workorder.create_workorder, "desc": "创建维修工单(幂等)",
                         "schema": {"store_id": "string", "equipment_id": "string", "fault": "string",
                                    "budget": "number", "idempotency_key": "string"}},
    "track_workorder": {"fn": workorder.track_workorder, "desc": "查询工单状态",
                        "schema": {"workorder_id": "string"}},
    "confirm_workorder_done": {"fn": workorder.confirm_done, "desc": "工单完工确认",
                               "schema": {"workorder_id": "string", "evidence": "object"}},
}


def _tools_list() -> list[dict]:
    """构造 MCP tools/list 响应。"""
    return [{
        "name": name,
        "description": t["desc"],
        "inputSchema": {"type": "object", "properties": t["schema"]},
    } for name, t in TOOLS.items()]


def _tool_call(name: str, arguments: dict) -> dict:
    """执行工具调用。"""
    if name not in TOOLS:
        return {"error": {"code": -32601, "message": f"未知工具: {name}"}}
    fn: Callable = TOOLS[name]["fn"]
    result = fn(**arguments)
    # ToolResult 是 dict 子类,直接返回
    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}],
            "isError": result.get("degraded", False) if isinstance(result, dict) else False}


class _MCPHandler(BaseHTTPRequestHandler):
    """JSON-RPC 2.0 over HTTP 请求处理器。"""

    def _send(self, code: int, body: Any) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _check_auth(self) -> bool:
        token = os.environ.get("MCP_TOKEN", "")
        if not token:
            return True  # 开发模式:无 token 要求
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {token}"

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_auth():
            self._send(401, {"jsonrpc": "2.0", "error": {"code": -32001, "message": "未授权"}})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"jsonrpc": "2.0", "error": {"code": -32700, "message": "解析错误"}})
            return
        method = req.get("method")
        rid = req.get("id")
        try:
            if method == "initialize":
                resp = {"jsonrpc": "2.0", "id": rid, "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "dianxun-mcp", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                }}
            elif method == "tools/list":
                resp = {"jsonrpc": "2.0", "id": rid, "result": {"tools": _tools_list()}}
            elif method == "tools/call":
                name = req.get("params", {}).get("name")
                args = req.get("params", {}).get("arguments", {})
                result = _tool_call(name, args)
                resp = {"jsonrpc": "2.0", "id": rid, "result": result}
            else:
                resp = {"jsonrpc": "2.0", "id": rid,
                        "error": {"code": -32601, "message": f"未知方法: {method}"}}
        except Exception as e:  # noqa: BLE001
            resp = {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32000, "message": f"{type(e).__name__}: {e}"}}
        self._send(200, resp)

    def do_GET(self) -> None:  # noqa: N802
        # 健康检查 + 工具清单概览
        self._send(200, {"service": "dianxun-mcp", "tools": len(TOOLS),
                         "endpoints": ["POST initialize", "POST tools/list", "POST tools/call"]})

    def log_message(self, fmt, *args):  # 静默默认日志
        pass


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    srv = ThreadingHTTPServer((host, port), _MCPHandler)
    token = os.environ.get("MCP_TOKEN", "")
    print(f"🔌 店巡 MCP Server 启动 http://{host}:{port}")
    print(f"   工具数: {len(TOOLS)} | 鉴权: {'Bearer token' if token else '开发模式(无鉴权)'}")
    print(f"   测试: curl -X POST http://{host}:{port} -d '{{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}}'")
    srv.serve_forever()


if __name__ == "__main__":
    main()
