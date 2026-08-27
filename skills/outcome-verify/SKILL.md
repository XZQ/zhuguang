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

## Change log

- 1.0.0: independent requery and separate device/goods/sales-hold verification.
