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

## Change log

- 1.0.0: stateful cold-chain facts, freshness, quality, and cause-free triage.
