"""Minimal Streamable HTTP / JSON-RPC adapter for the 12 stateful P0 tools."""

from __future__ import annotations

import hmac
import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from ..validation import validate_json
from .p0 import MCPService, default_service

LOGGER = logging.getLogger(__name__)
MAX_REQUEST_BYTES = 1024 * 1024


def _object_schema(
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


_STRING = {"type": "string", "minLength": 1}
_STRING_ARRAY = {"type": "array", "items": _STRING, "minItems": 1, "uniqueItems": True}

TOOLS: dict[str, dict[str, Any]] = {
    "query_device_context": {
        "method": "query_device_context",
        "description": "Query temperature series, health, door, power and maintenance context.",
        "actor": "Sentry",
        "inputSchema": _object_schema(
            {
                "device_id": _STRING,
                "store_id": _STRING,
                "incident_id": _STRING,
                "facets": {"type": "array", "items": _STRING, "uniqueItems": True},
                "window_minutes": {"type": "integer", "minimum": 1},
                "request_id": _STRING,
            }
        ),
    },
    "query_inventory_batches": {
        "method": "query_inventory_batches",
        "description": "Query device-linked batches and their storage policies.",
        "actor": "Diagnoser",
        "inputSchema": _object_schema(
            {
                "device_id": _STRING,
                "store_id": _STRING,
                "batch_ids": _STRING_ARRAY,
                "incident_id": _STRING,
                "request_id": _STRING,
            }
        ),
    },
    "query_sales_holds": {
        "method": "query_sales_holds",
        "description": "Query POS sales holds by incident, batch or status.",
        "actor": "Auditor",
        "inputSchema": _object_schema(
            {
                "incident_id": _STRING,
                "batch_ids": _STRING_ARRAY,
                "status": {"enum": ["active", "released"]},
                "request_id": _STRING,
            }
        ),
    },
    "query_workorder": {
        "method": "query_workorder",
        "description": "Query workorder and vendor status without inferring device recovery.",
        "actor": "Auditor",
        "inputSchema": _object_schema(
            {
                "workorder_id": _STRING,
                "action_id": _STRING,
                "incident_id": _STRING,
                "request_id": _STRING,
            }
        ),
    },
    "query_approval": {
        "method": "query_approval",
        "description": "Query approval status for one controlled action.",
        "actor": "Auditor",
        "inputSchema": _object_schema(
            {
                "approval_id": _STRING,
                "action_id": _STRING,
                "incident_id": _STRING,
                "request_id": _STRING,
            }
        ),
    },
    "apply_sales_hold": {
        "method": "apply_sales_hold",
        "description": "Apply an idempotent temporary batch sales hold.",
        "actor": "Executor",
        "inputSchema": _object_schema(
            {
                "incident_id": _STRING,
                "action_id": _STRING,
                "store_id": _STRING,
                "batch_ids": _STRING_ARRAY,
                "reason": _STRING,
                "idempotency_key": _STRING,
                "request_id": _STRING,
            },
            ["incident_id", "action_id", "store_id", "batch_ids", "reason", "idempotency_key"],
        ),
    },
    "release_sales_hold": {
        "method": "release_sales_hold",
        "description": "Release holds only with matching approval and Auditor verification.",
        "actor": "Executor",
        "inputSchema": _object_schema(
            {
                "incident_id": _STRING,
                "action_id": _STRING,
                "hold_ids": _STRING_ARRAY,
                "approval_id": _STRING,
                "verification_id": _STRING,
                "idempotency_key": _STRING,
                "request_id": _STRING,
            },
            [
                "incident_id",
                "action_id",
                "hold_ids",
                "approval_id",
                "verification_id",
                "idempotency_key",
            ],
        ),
    },
    "apply_batch_disposition": {
        "method": "apply_batch_disposition",
        "description": "Quarantine, transfer, release or dispose batches under policy.",
        "actor": "Executor",
        "inputSchema": _object_schema(
            {
                "incident_id": _STRING,
                "action_id": _STRING,
                "batch_ids": _STRING_ARRAY,
                "disposition": {"enum": ["quarantined", "transferred", "released", "disposed"]},
                "approval_id": _STRING,
                "idempotency_key": _STRING,
                "request_id": _STRING,
            },
            ["incident_id", "action_id", "batch_ids", "disposition", "idempotency_key"],
        ),
    },
    "create_workorder": {
        "method": "create_workorder",
        "description": "Create an idempotent repair workorder; high budgets require approval.",
        "actor": "Executor",
        "inputSchema": _object_schema(
            {
                "incident_id": _STRING,
                "action_id": _STRING,
                "store_id": _STRING,
                "device_id": _STRING,
                "fault": _STRING,
                "budget": {"type": "number", "minimum": 0},
                "approval_id": _STRING,
                "assignee": {"type": "string"},
                "idempotency_key": _STRING,
                "request_id": _STRING,
            },
            [
                "incident_id",
                "action_id",
                "store_id",
                "device_id",
                "fault",
                "budget",
                "idempotency_key",
            ],
        ),
    },
    "create_approval": {
        "method": "create_approval",
        "description": "Create a pending approval for one controlled action.",
        "actor": "Executor",
        "inputSchema": _object_schema(
            {
                "incident_id": _STRING,
                "action_id": _STRING,
                "subject": _STRING,
                "requested_action_type": _STRING,
                "timeout_minutes": {"type": "integer", "minimum": 1},
                "amount": {"type": "number", "minimum": 0},
                "disposition": {"type": "string"},
                "idempotency_key": _STRING,
                "request_id": _STRING,
            },
            [
                "incident_id",
                "action_id",
                "subject",
                "requested_action_type",
                "idempotency_key",
            ],
        ),
    },
    "decide_approval": {
        "method": "decide_approval",
        "description": "Human/ScenarioEngine-only approval decision.",
        "actor": None,
        "allowedActors": ["Human", "ScenarioEngine"],
        "inputSchema": _object_schema(
            {
                "approval_id": _STRING,
                "decision": {"enum": ["approved", "rejected", "timeout"]},
                "reason": _STRING,
                "idempotency_key": _STRING,
                "request_id": _STRING,
            },
            ["approval_id", "decision", "reason", "idempotency_key"],
        ),
    },
    "record_manual_evidence": {
        "method": "record_manual_evidence",
        "description": "Human/ScenarioEngine-only measurement or media reference record.",
        "actor": None,
        "allowedActors": ["Human", "ScenarioEngine"],
        "inputSchema": _object_schema(
            {
                "incident_id": _STRING,
                "action_id": _STRING,
                "evidence_type": _STRING,
                "observed_at": _STRING,
                "note": {"type": "string"},
                "metadata": {"type": "object"},
                "uri": {"type": "string"},
                "sha256": {"type": "string", "pattern": "^[a-fA-F0-9]{64}$"},
                "idempotency_key": _STRING,
                "request_id": _STRING,
            },
            [
                "incident_id",
                "evidence_type",
                "observed_at",
                "note",
                "metadata",
                "idempotency_key",
            ],
        ),
    },
}


def tools_list() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": tool["description"],
            "inputSchema": tool["inputSchema"],
        }
        for name, tool in TOOLS.items()
    ]


def tool_call(
    name: str,
    arguments: Any,
    *,
    actor: str | None = None,
    service: MCPService | None = None,
) -> dict[str, Any]:
    tool = TOOLS.get(name)
    if tool is None:
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
            "isError": True,
        }
    if not isinstance(arguments, dict):
        result = _adapter_error("INVALID_ARGUMENT", "tool arguments must be a JSON object")
        return _tool_result(result)
    validation_errors = validate_json(arguments, tool["inputSchema"], path="arguments")
    if validation_errors:
        result = _adapter_error(
            "INVALID_ARGUMENT",
            "; ".join(validation_errors[:5]),
            request_id=arguments.get("request_id", "unassigned"),
        )
        return _tool_result(result)
    resolved_actor = actor or tool.get("actor")
    allowed = tool.get("allowedActors")
    if allowed and resolved_actor not in allowed:
        result = _adapter_error(
            "FORBIDDEN",
            "Trusted human actor is required",
            request_id=arguments.get("request_id", "unassigned"),
        )
    else:
        clean_arguments = dict(arguments)
        clean_arguments["actor"] = resolved_actor
        try:
            fn = getattr(service or default_service(), tool["method"])
            result = fn(**clean_arguments)
        except (KeyError, TypeError, ValueError) as exc:
            result = _adapter_error(
                "INVALID_ARGUMENT",
                str(exc),
                request_id=arguments.get("request_id", "unassigned"),
            )
        except Exception:  # noqa: BLE001 - adapter must return a stable boundary
            LOGGER.exception("Unhandled MCP tool failure for %s", name)
            result = _adapter_error(
                "INTERNAL_ERROR",
                "The tool failed unexpectedly; inspect server logs with the request_id",
                request_id=arguments.get("request_id", "unassigned"),
            )
    return _tool_result(result)


def _tool_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}],
        "isError": not result.get("ok", False),
    }


def _adapter_error(
    code: str,
    message: str,
    *,
    request_id: str = "unassigned",
) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": {"code": code, "message": message},
        "request_id": request_id,
        "source": "dianxun-mcp-adapter",
        "source_ts": "",
        "partial": False,
        "audit_ref": None,
    }


class MCPHandler(BaseHTTPRequestHandler):
    server_version = "DianxunMCP/0.2"

    def _send(self, code: int, body: Any) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authenticate(self) -> tuple[bool, str | None]:
        mapping_raw = os.environ.get("MCP_ACTOR_TOKENS_JSON", "")
        single_token = os.environ.get("MCP_TOKEN", "")
        auth = self.headers.get("Authorization", "")
        supplied = auth.removeprefix("Bearer ") if auth.startswith("Bearer ") else ""
        if mapping_raw:
            if not supplied:
                return False, None
            try:
                mapping = json.loads(mapping_raw)
            except json.JSONDecodeError:
                return False, None
            if not isinstance(mapping, dict):
                return False, None
            actor = mapping.get(supplied)
            return isinstance(actor, str) and bool(actor), actor if isinstance(actor, str) else None
        if single_token:
            return bool(supplied) and hmac.compare_digest(supplied, single_token), None
        return True, None

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/mcp":
            self._send(404, {"error": "Not found"})
            return
        authenticated, actor = self._authenticate()
        if not authenticated:
            self._send(
                401,
                {"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unauthorized"}},
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("invalid content length")
            request = json.loads(
                self.rfile.read(length),
                parse_constant=_reject_nonfinite,
            )
        except (ValueError, json.JSONDecodeError):
            self._send(
                400,
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}},
            )
            return
        if not isinstance(request, dict):
            self._send(
                400,
                {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}},
            )
            return
        method = request.get("method")
        request_id = request.get("id")
        if method == "initialize":
            result: Any = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "dianxun-mcp", "version": "0.2.0"},
                "capabilities": {"tools": {}},
            }
        elif method == "tools/list":
            result = {"tools": tools_list()}
        elif method == "tools/call":
            params = request.get("params", {})
            if not isinstance(params, dict):
                self._send(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32602, "message": "Invalid params"},
                    },
                )
                return
            result = tool_call(
                params.get("name", ""),
                params.get("arguments", {}),
                actor=actor,
            )
        else:
            self._send(
                200,
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Unknown method: {method}"},
                },
            )
            return
        self._send(200, {"jsonrpc": "2.0", "id": request_id, "result": result})

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self._send(404, {"error": "Not found"})
            return
        self._send(
            200,
            {"service": "dianxun-mcp", "version": "0.2.0", "tools": len(TOOLS)},
        )

    def log_message(self, format: str, *args: Any) -> None:
        return


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is not allowed: {value}")


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), MCPHandler)
    print(f"Dianxun MCP listening on http://{host}:{port} with {len(TOOLS)} tools")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
