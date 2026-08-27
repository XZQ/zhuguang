# review-report

- Version: `1.0.0`
- Priority: P0
- Agent: Auditor
- Entrypoint: `dianxun.skills.review_incident`

## Purpose

Generate an incident-scoped review that links each batch to its own actions and verifications. It emits knowledge candidates but does not claim RAG retrieval or auto-publish production knowledge.

## Contract

- Input: [`input.schema.json`](input.schema.json)
- Output: [`output.schema.json`](output.schema.json)
- Examples: [`examples.json`](examples.json)
- Permissions: Incident/Trace read and controlled knowledge-candidate write.
- Errors: `INCIDENT_NOT_RESOLVED`, `TRACE_PARTIAL`, `EVIDENCE_INCOMPLETE`.
- Degradation: mark partial evidence and keep the knowledge candidate pending human review.
- Quality metric: per-batch linkage completeness and trace completeness.

## Change log

- 1.0.0: incident/batch association and truthful P1 RAG-disabled status.
