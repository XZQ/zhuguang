---
name: coldchain-risk-assess
description: Assess time-temperature exposure and batch safety without treating device recovery as product safety.
---

# coldchain-risk-assess

- Version: `1.0.0`
- Priority: P0
- Agent: Diagnoser
- Entrypoint: `dianxun.skills.coldchain_risk_assess`

## Purpose

Calculate batch-specific time-temperature exposure from versioned demo policy and recommend `quarantined`, `transferred`, `released`, or `disposed`. The Skill never performs the disposition and never authorizes release.

## Contract

- Input: [`input.schema.json`](input.schema.json)
- Output: [`output.schema.json`](output.schema.json)
- Examples: [`examples.json`](examples.json)
- Permissions: read-only Incident and policy context.
- Errors: `SERIES_MISSING`, `POLICY_MISSING`, `INVALID_BATCH`.
- Degradation: recommend quarantine when evidence is incomplete.
- Quality metric: batch-level recommendation accuracy and unsafe-release count.

## AgentTeams execution

1. Use the device temperature series and `query_inventory_batches` result referenced by the current incident; requery if the references are stale.
2. Evaluate each batch independently against its storage limits and the versioned policy named in the input.
3. Emit one recommendation per batch with exposure, evidence refs, confidence, and reason. Never call `apply_batch_disposition` or authorize release.
4. If the series, policy, or batch mapping is incomplete, return degraded evidence and recommend `quarantined`.

## Change log

- 1.0.0: trapezoidal degree-minute assessment with batch-specific limits.
