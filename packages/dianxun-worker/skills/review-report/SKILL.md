---
name: review-report
description: Produce an evidence-linked incident review without claiming unimplemented retrieval or learning effects.
---

# review-report

- Version: `1.1.0`
- Priority: P0
- Agent: Auditor
- Entrypoint: `dianxun.skills.review_incident`

## Purpose

Generate an incident-scoped review that links each batch to its own actions and verifications. It emits knowledge candidates but does not claim RAG retrieval or auto-publish production knowledge.

## Contract

- Input: [`input.schema.json`](input.schema.json)
- Output: [`output.schema.json`](output.schema.json)
- Examples: [`examples.json`](examples.json)
- Permissions: Incident/Trace read and controlled `create_knowledge_candidate`; no publication permission.
- Errors: `INCIDENT_NOT_RESOLVED`, `TRACE_PARTIAL`, `EVIDENCE_INCOMPLETE`.
- Degradation: mark partial evidence and keep the knowledge candidate pending human review.
- Quality metric: per-batch linkage completeness, trace completeness, and zero unreviewed retrievals.

## AgentTeams execution

1. Run only after outcome verification has produced a safe resolved result.
2. Build the report from current incident handoffs and MCP evidence refs; link every affected batch to its own actions and verification.
3. Record limitations, partial traces, waiting states, and failed attempts instead of omitting them.
4. Call `dianxun-mcp.create_knowledge_candidate` with tenant, incident, trace, dedupe basis, confidence, redaction-pending state, and source evidence IDs.
5. Emit knowledge candidates as pending artifacts. Auditor cannot call `review_knowledge_candidate`; do not claim publication, retrieval, or accuracy improvement without separate evidence.

## Change log

- 1.1.0: persists deduplicated pending candidates through the optional P1 MCP boundary while preserving human-only publication.
- 1.0.0: incident/batch association and truthful P1 RAG-disabled status.
