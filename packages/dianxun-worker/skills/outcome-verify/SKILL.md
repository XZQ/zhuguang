---
name: outcome-verify
description: Independently requery device, goods, hold, approval, and work-order state before recommending closure.
---

# outcome-verify

- Version: `1.0.0`
- Priority: P0
- Agent: Auditor
- Entrypoint: `dianxun.skills.outcome_verify`

## Purpose

Independently requery device, batch, sales-hold, workorder, approval, and audit state. It records Auditor verifications and returns `verified`, `reopened`, or `manual_review`; Executor receipts are never sufficient evidence.

## Contract

- Input: [`input.schema.json`](input.schema.json)
- Output: [`output.schema.json`](output.schema.json)
- Examples: [`examples.json`](examples.json)
- Permissions: five P0 query MCPs and verification records; no business-state writes.
- Errors: `QUERY_PARTIAL`, `DEVICE_NOT_RECOVERED`, `GOODS_UNSAFE`, `APPROVAL_INCOMPLETE`.
- Degradation: keep holds active and return manual review or reopen.
- Quality metric: safe-closure rate, false-closure rate, evidence completeness.

## AgentTeams execution

1. Independently call all applicable queries: device context, inventory batches, sales holds, work order, and approval.
2. Compare fresh tool state with the incident acceptance criteria; do not use Executor's success flag as evidence.
3. Verify device recovery, goods disposition, active holds, approval, and work-order state as separate gates.
4. Return `verified` only when every required gate passes. Otherwise return `reopened` or `manual_review`, keep unsafe holds active, and cite the blocking evidence.

## Change log

- 1.0.0: independent requery and separate device/goods/sales-hold verification.
