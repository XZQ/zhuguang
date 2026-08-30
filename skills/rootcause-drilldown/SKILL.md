---
name: rootcause-drilldown
description: Rank evidence-backed cold-chain root-cause hypotheses and the next checks needed to distinguish them.
---

# rootcause-drilldown

- Version: `1.2.0`
- Priority: P0
- Agent: Diagnoser
- Entrypoint: `dianxun.skills.diagnose_coldchain_hypotheses`

## Purpose

Produce evidence-linked Top-K hypotheses with supporting evidence, contradictions, missing evidence, and next checks. Cross-store comparison is optional supporting evidence and never proves the cause.

## Contract

- Input: [`input.schema.json`](input.schema.json)
- Output: [`output.schema.json`](output.schema.json)
- Examples: [`examples.json`](examples.json)
- Permissions: `query_device_context` and optional P1 `search_knowledge`; no business writes.
- Errors: `DEVICE_CONTEXT_UNAVAILABLE`, `INSUFFICIENT_EVIDENCE`, `INVALID_INPUT`.
- Degradation: return an explicit low-confidence `insufficient_evidence` hypothesis.
- Quality metric: Top-3 cause accuracy, unsupported-claim count, labeled Recall@3, and citation completeness.

## AgentTeams execution

1. Call `dianxun-mcp.query_device_context` with temperature, reading quality, health, door, power, and maintenance facets; use incident-bound manual evidence when available.
2. When P1 tools are enabled, call `dianxun-mcp.search_knowledge`; only `published + redaction passed` entries may be returned, and every hit must retain its source incident, trace, evidence IDs, and quoted span.
3. Rank at most three hypotheses; for each, separate supporting evidence, contradictions, missing evidence, and next checks. A RAG hit is supporting context, never proof of causation.
4. Reference MCP evidence IDs and request IDs. Do not claim a cause is confirmed merely because it ranks first.
5. When retrieval is disabled or returns no hits, report that state explicitly. Do not fabricate a historical case.
6. Treat `suspect` or `bad` temperature readings as a sensor-quality hypothesis, not as proof of product exposure; require independent corroboration.

## Change log

- 1.2.0: optional quality-gated knowledge retrieval with source citations and labeled retrieval metrics.
- 1.1.0: ranks sensor, door, power, and compressor hypotheses from reading quality and manual corroboration.
- 1.0.0: replaces single-root-cause output with evidence-linked Top-K hypotheses.
