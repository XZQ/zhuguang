---
name: work-order-dispatch
description: Create an idempotent repair work order only after policy and approval requirements are satisfied.
---

# work-order-dispatch

- Version: `1.0.0`
- Priority: P0
- Agent: Executor
- Entrypoint: `dianxun.skills.dispatch_stateful_workorder`

## Purpose

Requery approval state and create an idempotent repair workorder through the stateful MCP boundary. A pending, rejected, or timed-out approval never authorizes dispatch.

## Contract

- Input: [`input.schema.json`](input.schema.json)
- Output: [`output.schema.json`](output.schema.json)
- Examples: [`examples.json`](examples.json)
- Permissions: `query_approval`, controlled `create_workorder`.
- Errors: `APPROVAL_REQUIRED`, `APPROVAL_INVALID`, `TOOL_FAILURE`, `INVALID_STATE`.
- Compensation: cancel or reassign; payment is prohibited.
- Quality metric: unauthorized dispatch count, duplicate side effects, tool success rate.

## AgentTeams execution

1. When policy requires approval, call `dianxun-mcp.create_approval` once with the action ID and idempotency key, then requery it with `query_approval`.
2. Call `dianxun-mcp.create_workorder` only when the required approval is `approved`; reuse a stable idempotency key on retries.
3. For pending, rejected, timeout, partial, or tool failure, create no controlled work order and report the blocking owner/deadline while containment stays active.
4. Return the work-order receipt, request ID, audit ref, and compensation metadata. Never perform payment.

## Change log

- 1.0.0: stateful approval recheck, idempotency, audit reference, and compensation metadata.
