---
name: rootcause-drilldown
description: Rank evidence-backed cold-chain root-cause hypotheses and the next checks needed to distinguish them.
---

# rootcause-drilldown

- Version: `1.0.0`
- Priority: P0
- Agent: Diagnoser
- Entrypoint: `dianxun.skills.diagnose_coldchain_hypotheses`

## Purpose

Produce evidence-linked Top-K hypotheses with supporting evidence, contradictions, missing evidence, and next checks. Cross-store comparison is optional supporting evidence and never proves the cause.

## Contract

- Input: [`input.schema.json`](input.schema.json)
- Output: [`output.schema.json`](output.schema.json)
- Examples: [`examples.json`](examples.json)
- Permissions: `query_device_context`; no business writes.
- Errors: `DEVICE_CONTEXT_UNAVAILABLE`, `INSUFFICIENT_EVIDENCE`, `INVALID_INPUT`.
- Degradation: return an explicit low-confidence `insufficient_evidence` hypothesis.
- Quality metric: Top-3 cause accuracy and unsupported-claim count.

## AgentTeams execution

1. Call `dianxun-mcp.query_device_context` with temperature, health, door, power, and maintenance facets.
2. Rank at most three hypotheses; for each, separate supporting evidence, contradictions, missing evidence, and next checks.
3. Reference MCP evidence IDs and request IDs. Do not claim a cause is confirmed merely because it ranks first.
4. Do not call write tools or claim a RAG hit without an actual retrieval result.

## Change log

- 1.0.0: replaces single-root-cause output with evidence-linked Top-K hypotheses.
