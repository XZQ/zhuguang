# Task 4 backend implementation report

Implemented scope-v2 cutover, runtime fencing, exact approvals and a closable revised workflow. No production service, credentials, hosted database or third-party session was used.

## Contracts and implementation

- Explicit offline command: `dianxun migrate-scope-v2 --db TARGET --backup-verified --writers-stopped`. Existing migration remains transactional and does not clear data. Flags are operator attestations; the command does not claim to perform or test a backup. Readiness checks the schema when the migration marker exists or `DIANXUN_SCOPE_V2_REQUIRED=1`.
- After activation, `runtime_open` requires `expected_scope_version: 0` for a new ID and creates version 1 with a canonical DB snapshot, `scope_state: reconciled`, and a source revision/audit record. Nonactivated deterministic fixtures retain the legacy protocol. Explicit current scope is required at the runtime call boundary and all incident MCP mutations; omitted/bool/stale values are rejected. Legacy migrated records remain `requires_reconciliation` until Human attestation.
- `runtime_reconcile_scope` takes `incident_id`, `expected_versions` (same per-incident scope/context map as revise), `change_id`, and `source_ref`; a registered same-store Human attests server-read inventory. All related open incidents are updated in one transaction. No inventory rows or successful channel receipts are fabricated.
- `runtime_open` accepts paired `previous_incident_id` / `source_ref` for a closed same-store/same-asset predecessor. The new context and initial revision retain the source link; closed aggregate history is protected from saves.
- MCP actions and approvals persist scope/target snapshots. Workorders approve exactly one device; goods and release approvals name exact batch objects. Decision and execution recheck quantity, location, policy, action identity and expiration. Unchanged approvals survive unrelated growth; affected unconsumed approvals become `requires_review` without rewriting their historical decision.
- Shared PostgreSQL advisory mutex uses the same tenant/store key for runtime, direct MCP, independent verification, aggregate recomputation and closing. SQLite uses its existing immediate transaction. Revision also includes open incidents on a move destination.
- Scope revision archives checkpoints, cancels old assignments/main leases, starts a new generation and resumes bounded progression. Old successful actions/receipts remain unchanged; repair creation cannot duplicate an existing same-device workorder. Unknown operation outcomes remain blocked for reconciliation.
- Exact historical MCP/runtime receipt replay is read-only and marked `historical_replay`; it cannot update the current checkpoint or generation. Different request content retains idempotency conflicts. Old completed checkpoint replay reads archived history.
- Auditor, release and close check the current full inventory snapshot, source reconciliation, current leaf action bindings and independent evidence. Auditor also queries moved-goods destinations. Verification IDs are suffixed `:scope:<version>` and persisted verification rows bind scope version/digest. A parent or prechange terminal status alone cannot cover changed leaf quantities/locations.
- Export schema now permits `reconciled`; the default remains empty for legacy records and migration still emits `requires_reconciliation`.
- Requested Task 6 follow-up: the panel labels lineage as `关联批次共享谱系` and explains cross-incident membership. Truncated revisions also mark lineage truncated because missing historical IDs can omit ancestors. Existing dossier test contains label/limit assertions.

## Focused verification completed

- `.venv/bin/python -m unittest tests.test_scope_revision tests.test_scope_approval tests.test_scope_migration -q`: 17 passed before the additional approval race case.
- `.venv/bin/python -m unittest tests.test_scope_workflow tests.test_scope_revision tests.test_scope_approval tests.test_scope_migration -q`: 21 passed at that checkpoint (four workflow tests plus the prior 17).
- Added release guard negative and dossier follow-up: two focused tests passed.
- Added approval-decision versus split race: focused test passed. Either the decision commits on version 1 then loses applicability, or the stale decision is rejected; children never inherit authorization.
- The real isolated localhost workflow exercised detect/contain/repair, split P into C1/C2, fresh child approvals/disposal receipts, add C3, runtime restart, fresh C3 action/evidence, independent audits and `CLOSED` at scope 3. It asserted one repair order and byte-equivalent original action rows. It also checked read-only old-lease receipt replay and a new source-linked incident after close.
- Negative cases exercise stale/missing scope, unknown outcomes, unexplained quantity changes until Human reconciliation, old release guard after unrelated growth, split conservation, multi-incident CAS and transactional rollback.
- `ruff check` on all modified Python files and `git diff --check`: passed. Only touched files were formatted.
- `tests/scope_revision_pg_checks.py` now reuses revision, approval and full runtime workflow tests with fresh isolated PostgreSQL databases and a distinct restricted runtime login. Main agent owns the pending final PostgreSQL and full-suite run; this report does not claim those passed.

## Practical boundaries

- Human source references and synthetic receipts remain asserted/synthetic provenance, not independently connected WMS/POS or a real field approval system. Real source trust, hosted migration/backup restore, external channels and operational rollout remain separate acceptance work.
- Repair deduplication intentionally refuses a second same-device workorder in the same incident; future genuinely new faults need an explicit follow-up incident/repair model, rather than laundering a scope revision into a duplicate side effect.
- Migrated inventory that is missing or structurally invalid remains blocked until an authorized source repair can establish a complete snapshot. The reconciliation endpoint does not invent missing stock or discard responsibility.
- Final integration/PG verification follows this commit. No broad repeated suite was run by this subtask.
