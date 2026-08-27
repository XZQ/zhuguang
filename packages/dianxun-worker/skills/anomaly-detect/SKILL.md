---
name: anomaly-detect
description: Detect and triage sustained cold-chain anomalies from current device and batch evidence.
---

# anomaly-detect

- Version: `1.0.0`
- Priority: P0
- Agent: Sentry
- Entrypoint: `dianxun.skills.detect_coldchain_event`

## Purpose

Read current device and inventory facts, evaluate freshness and sustained temperature risk, and emit a containment request. It reports observations only; it does not infer a confirmed root cause or perform writes.

## Contract

- Input: [`input.schema.json`](input.schema.json)
- Output: [`output.schema.json`](output.schema.json)
- Examples: [`examples.json`](examples.json)
- Permissions: `query_device_context`, `query_inventory_batches`
- Errors: `SOURCE_UNAVAILABLE`, `PARTIAL_EVIDENCE`, `INVALID_INPUT`
- Degradation: preserve `partial=true`, request containment, and never invent missing evidence.
- Quality metric: event detection and critical Evidence-field completeness.

## AgentTeams execution

1. Call `dianxun-mcp.query_device_context` for the requested device and time window.
2. Call `dianxun-mcp.query_inventory_batches` for the same device.
3. Preserve every returned `request_id`, evidence ID, freshness, quality, and `partial` flag.
4. Emit the output-schema fields and a containment request when sustained risk or incomplete safety evidence exists. Do not call write tools.

## Change log

- 1.0.0: stateful cold-chain facts, freshness, quality, and cause-free triage.
