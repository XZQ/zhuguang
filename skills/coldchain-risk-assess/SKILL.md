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

## Change log

- 1.0.0: trapezoidal degree-minute assessment with batch-specific limits.
