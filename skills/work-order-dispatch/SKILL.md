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

## Change log

- 1.0.0: stateful approval recheck, idempotency, audit reference, and compensation metadata.
