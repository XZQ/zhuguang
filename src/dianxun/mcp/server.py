"""Minimal Streamable HTTP / JSON-RPC adapter for the 12 stateful P0 tools."""

from __future__ import annotations

import hmac
import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from time import perf_counter
from typing import Any

from .. import trace
from ..metrics import MCPMetrics
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
        "properties": {
            "runtime_trace_id": {"type": "string", "minLength": 1},
            **properties,
        },
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
        "allowedActors": ["Sentry", "Diagnoser", "Auditor", "AuthenticatedClient"],
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
        "allowedActors": ["Sentry", "Diagnoser", "Auditor", "AuthenticatedClient"],
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
        "allowedActors": ["Auditor", "AuthenticatedClient"],
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
        "allowedActors": ["Auditor", "AuthenticatedClient"],
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
        "allowedActors": ["Executor", "Auditor", "AuthenticatedClient"],
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
        "allowedActors": ["Executor"],
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
        "allowedActors": ["Executor"],
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
        "allowedActors": ["Executor"],
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
        "allowedActors": ["Executor"],
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
        "allowedActors": ["Executor"],
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

P1_TOOLS: dict[str, dict[str, Any]] = {
    "search_knowledge": {
        "method": "search_knowledge",
        "description": "Retrieve only reviewed, redaction-passed incident knowledge.",
        "actor": "Diagnoser",
        "allowedActors": ["Diagnoser", "AuthenticatedClient"],
        "inputSchema": _object_schema(
            {
                "tenant_id": _STRING,
                "query": _STRING,
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
                "minimum_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "request_id": _STRING,
            },
            ["tenant_id", "query"],
        ),
    },
    "create_knowledge_candidate": {
        "method": "create_knowledge_candidate",
        "description": "Create a pending incident knowledge candidate; never auto-publish it.",
        "actor": "Auditor",
        "allowedActors": ["Auditor"],
        "inputSchema": _object_schema(
            {
                "tenant_id": _STRING,
                "incident_id": _STRING,
                "trace_id": _STRING,
                "title": _STRING,
                "body": _STRING,
                "tags": {"type": "array", "items": _STRING, "uniqueItems": True},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "source_evidence_ids": {
                    "type": "array",
                    "items": _STRING,
                    "uniqueItems": True,
                },
                "dedupe_key": _STRING,
                "request_id": _STRING,
            },
            [
                "tenant_id",
                "incident_id",
                "trace_id",
                "title",
                "body",
                "tags",
                "confidence",
                "source_evidence_ids",
            ],
        ),
    },
    "review_knowledge_candidate": {
        "method": "review_knowledge_candidate",
        "description": "Human-only redaction and publication decision for one candidate.",
        "actor": None,
        "allowedActors": [
            "Human",
            "food_safety_owner",
            "hq_reviewer",
            "knowledge_reviewer",
        ],
        "inputSchema": _object_schema(
            {
                "knowledge_id": _STRING,
                "decision": {"enum": ["approve", "reject"]},
                "reason": _STRING,
                "redaction_passed": {"type": "boolean"},
                "request_id": _STRING,
            },
            ["knowledge_id", "decision", "reason", "redaction_passed"],
        ),
    },
}

_READ_ONLY_TOOLS = {
    name for name in (*TOOLS, *P1_TOOLS) if name.startswith("query_") or name == "search_knowledge"
}
_KNOWN_ACTORS = {
    actor
    for definition in (*TOOLS.values(), *P1_TOOLS.values())
    for actor in ([definition.get("actor")] + definition.get("allowedActors", []))
    if actor
}

for _definition in (*TOOLS.values(), *P1_TOOLS.values()):
    _definition["inputSchema"]["properties"]["runtime_trace_id"] = _STRING

MCP_METRICS = MCPMetrics((*TOOLS, *P1_TOOLS))


def enabled_tools() -> dict[str, dict[str, Any]]:
    if os.environ.get("DIANXUN_ENABLE_P1_TOOLS") == "1":
        return {**TOOLS, **P1_TOOLS}
    return TOOLS


def tools_list() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": tool["description"],
            "inputSchema": tool["inputSchema"],
        }
        for name, tool in enabled_tools().items()
    ]


def tool_call(
    name: str,
    arguments: Any,
    *,
    actor: str | None = None,
    service: MCPService | None = None,
) -> dict[str, Any]:
    started = perf_counter()
    result: dict[str, Any] | None = None
    try:
        result = _execute_tool_call(name, arguments, actor=actor, service=service)
        return result
    finally:
        MCP_METRICS.observe_tool_call(
            name,
            success=bool(result) and not result.get("isError", True),
            duration=perf_counter() - started,
        )


def _execute_tool_call(
    name: str,
    arguments: Any,
    *,
    actor: str | None = None,
    service: MCPService | None = None,
) -> dict[str, Any]:
    if not isinstance(name, str):
        result = _adapter_error("INVALID_ARGUMENT", "tool name must be a string")
        return _tool_result(result)
    tool = enabled_tools().get(name)
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
            f"Actor {resolved_actor or 'anonymous'} is not authorized for {name}",
            request_id=arguments.get("request_id", "unassigned"),
        )
    else:
        clean_arguments = dict(arguments)
        runtime_trace_id = clean_arguments.pop("runtime_trace_id", None)
        clean_arguments["actor"] = resolved_actor
        try:
            fn = getattr(service or default_service(), tool["method"])
            if runtime_trace_id:
                with trace.span(
                    name,
                    "mcp",
                    runtime_trace_id,
                    input={
                        "actor": resolved_actor,
                        "argument_keys": sorted(clean_arguments),
                        "incident_id": clean_arguments.get("incident_id"),
                    },
                ) as tool_span:
                    result = fn(**clean_arguments)
                    tool_span.output = {
                        "ok": result.get("ok"),
                        "request_id": result.get("request_id"),
                        "audit_ref": result.get("audit_ref"),
                    }
            else:
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
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, code: int, body: str, content_type: str) -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authenticate(self) -> tuple[bool, str | None, str]:
        mapping_raw = os.environ.get("MCP_ACTOR_TOKENS_JSON", "")
        single_token = os.environ.get("MCP_TOKEN", "")
        auth = self.headers.get("Authorization", "")
        supplied = auth.removeprefix("Bearer ") if auth.startswith("Bearer ") else ""
        if mapping_raw:
            if not supplied:
                return False, None, "actor_bound"
            try:
                mapping = json.loads(mapping_raw)
            except json.JSONDecodeError:
                return False, None, "actor_bound"
            if not isinstance(mapping, dict):
                return False, None, "actor_bound"
            actor = next(
                (
                    candidate
                    for token, candidate in mapping.items()
                    if isinstance(token, str)
                    and hmac.compare_digest(supplied, token)
                    and isinstance(candidate, str)
                ),
                None,
            )
            return bool(actor), actor, "actor_bound"
        if single_token:
            authenticated = bool(supplied) and hmac.compare_digest(supplied, single_token)
            return authenticated, None, "shared"
        return True, None, "anonymous"

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/mcp":
            self._send(404, {"error": "Not found"})
            return
        authenticated, actor, auth_mode = self._authenticate()
        if not authenticated:
            MCP_METRICS.record_auth_failure()
            self._send(
                401,
                {"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unauthorized"}},
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length > MAX_REQUEST_BYTES:
            self.rfile.read(MAX_REQUEST_BYTES + 1)
            self.close_connection = True
            self._send(
                400,
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}},
            )
            return
        try:
            if length <= 0:
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
            tool_name = params.get("name", "")
            if auth_mode == "shared" and tool_name not in _READ_ONLY_TOOLS:
                result = _tool_result(
                    _adapter_error(
                        "FORBIDDEN",
                        "An actor-bound token is required for state-changing tools",
                        request_id=(params.get("arguments") or {}).get("request_id", "unassigned")
                        if isinstance(params.get("arguments"), dict)
                        else "unassigned",
                    )
                )
            else:
                result = tool_call(
                    tool_name,
                    params.get("arguments", {}),
                    actor="AuthenticatedClient" if auth_mode == "shared" else actor,
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
        if self.path == "/metrics":
            self._send_text(
                200,
                MCP_METRICS.render_prometheus(),
                "text/plain; version=0.0.4; charset=utf-8",
            )
            return
        if self.path != "/health":
            self._send(404, {"error": "Not found"})
            return
        self._send(
            200,
            {
                "service": "dianxun-mcp",
                "version": "0.2.0",
                "tools": len(enabled_tools()),
                "p0_tools": len(TOOLS),
                "p1_knowledge_enabled": os.environ.get("DIANXUN_ENABLE_P1_TOOLS") == "1",
            },
        )

    def log_message(self, format: str, *args: Any) -> None:
        return


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is not allowed: {value}")


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    _validate_server_auth(host)
    server = ThreadingHTTPServer((host, port), MCPHandler)
    print(f"Dianxun MCP listening on http://{host}:{port} with {len(enabled_tools())} tools")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _validate_server_auth(host: str) -> None:
    mapping_raw = os.environ.get("MCP_ACTOR_TOKENS_JSON", "")
    shared_token = os.environ.get("MCP_TOKEN", "")
    if mapping_raw:
        try:
            mapping = json.loads(mapping_raw)
        except json.JSONDecodeError as exc:
            raise SystemExit("MCP_ACTOR_TOKENS_JSON must be a valid JSON object") from exc
        if (
            not isinstance(mapping, dict)
            or not mapping
            or any(
                not isinstance(token, str) or not token or actor not in _KNOWN_ACTORS
                for token, actor in mapping.items()
            )
        ):
            raise SystemExit("MCP_ACTOR_TOKENS_JSON must map non-empty tokens to declared actors")
    if host.casefold() not in {"127.0.0.1", "localhost", "::1"} and not (
        mapping_raw or shared_token
    ):
        raise SystemExit("Refusing a non-loopback MCP bind without authentication")


if __name__ == "__main__":
    main()
