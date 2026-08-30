CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stores (
    store_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    model TEXT NOT NULL,
    health_state TEXT NOT NULL,
    door_state TEXT NOT NULL,
    power_state TEXT NOT NULL,
    compressor_state TEXT NOT NULL,
    ambient_temp_c REAL NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS device_readings (
    reading_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    observed_at TIMESTAMPTZ NOT NULL,
    temp_c REAL NOT NULL,
    quality TEXT NOT NULL,
    source TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_device_readings
    ON device_readings(device_id, observed_at);

CREATE TABLE IF NOT EXISTS inventory_batches (
    batch_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    sku_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    storage_min_c REAL NOT NULL,
    storage_max_c REAL NOT NULL,
    disposition TEXT NOT NULL,
    safe_for_sale SMALLINT NOT NULL CHECK (safe_for_sale IN (0, 1)),
    policy_ref TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_batches_device ON inventory_batches(device_id);

CREATE TABLE IF NOT EXISTS sales_holds (
    hold_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    batch_id TEXT,
    sku_id TEXT,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL,
    released_at TIMESTAMPTZ,
    approval_id TEXT,
    verification_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_holds_incident ON sales_holds(incident_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_hold_incident_batch
    ON sales_holds(incident_id, batch_id)
    WHERE status = 'active' AND batch_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL,
    approvers_json JSONB NOT NULL,
    deadline TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    decided_at TIMESTAMPTZ,
    decided_by TEXT,
    decision_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_approvals_action ON approvals(action_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_approvals_action ON approvals(action_id);

CREATE TABLE IF NOT EXISTS workorders (
    workorder_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    fault TEXT NOT NULL,
    budget REAL NOT NULL,
    status TEXT NOT NULL,
    assignee TEXT,
    completion_evidence_json JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workorders_incident ON workorders(incident_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_workorders_action ON workorders(action_id);

CREATE TABLE IF NOT EXISTS manual_evidence (
    evidence_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    action_id TEXT,
    actor TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    uri TEXT,
    note TEXT,
    sha256 TEXT NOT NULL,
    metadata_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    phase TEXT NOT NULL,
    incident_status TEXT NOT NULL,
    work_status TEXT NOT NULL,
    case_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
    action_type TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    approval_id TEXT,
    request_json JSONB NOT NULL,
    response_json JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_actions_incident ON actions(incident_id);

CREATE TABLE IF NOT EXISTS verifications (
    verification_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
    subject TEXT NOT NULL,
    result TEXT NOT NULL,
    verifier TEXT NOT NULL,
    evidence_ids_json JSONB NOT NULL,
    expected_json JSONB NOT NULL,
    observed_json JSONB NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verifications_incident
    ON verifications(incident_id, subject);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    trace_id TEXT,
    tenant_id TEXT,
    actor TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    incident_id TEXT,
    action_id TEXT,
    policy_id TEXT,
    policy_version TEXT,
    policy_source_ref TEXT,
    request_json JSONB NOT NULL,
    response_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (audit_id, created_at)
) PARTITION BY RANGE (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_log(request_id);
CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_log(trace_id, created_at);

CREATE OR REPLACE FUNCTION ensure_audit_partition(month_start DATE)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    partition_name TEXT := 'audit_log_' || to_char(month_start, 'YYYYMM');
    month_end DATE := (month_start + INTERVAL '1 month')::DATE;
BEGIN
    IF month_start <> date_trunc('month', month_start)::DATE THEN
        RAISE EXCEPTION 'audit partition month_start must be the first day of a month';
    END IF;
    IF month_start < (date_trunc('month', CURRENT_DATE) - INTERVAL '12 months')::DATE
       OR month_start > (date_trunc('month', CURRENT_DATE) + INTERVAL '3 months')::DATE THEN
        RAISE EXCEPTION 'audit partition month is outside the allowed maintenance window';
    END IF;
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_log FOR VALUES FROM (%L) TO (%L)',
        partition_name,
        month_start,
        month_end
    );
    IF to_regprocedure('public.dianxun_tenant_allowed(text)') IS NOT NULL THEN
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', partition_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', partition_name);
        EXECUTE format('DROP POLICY IF EXISTS audit_partition_scope ON %I', partition_name);
        EXECUTE format(
            'CREATE POLICY audit_partition_scope ON %I USING '
            || '(public.dianxun_tenant_allowed(tenant_id)) WITH CHECK '
            || '(public.dianxun_tenant_allowed(tenant_id))',
            partition_name
        );
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION ensure_audit_partition(DATE) FROM PUBLIC;

SELECT ensure_audit_partition(date_trunc('month', CURRENT_DATE)::DATE);
SELECT ensure_audit_partition((date_trunc('month', CURRENT_DATE) + INTERVAL '1 month')::DATE);

CREATE TABLE IF NOT EXISTS idempotency (
    idempotency_key TEXT PRIMARY KEY,
    tenant_id TEXT,
    tool_name TEXT NOT NULL,
    response_json JSONB NOT NULL,
    audit_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_failures (
    tool_name TEXT PRIMARY KEY,
    remaining_calls INTEGER NOT NULL,
    error_code TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_items (
    knowledge_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    source_incident_id TEXT NOT NULL,
    source_trace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags_json JSONB NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    redaction_status TEXT NOT NULL CHECK (redaction_status IN ('pending', 'passed', 'failed')),
    review_status TEXT NOT NULL CHECK (review_status IN ('pending', 'published', 'rejected')),
    source_evidence_ids_json JSONB NOT NULL,
    embedding vector,
    embedding_model TEXT,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_reason TEXT,
    UNIQUE (tenant_id, dedupe_key)
);
CREATE INDEX IF NOT EXISTS idx_knowledge_quality
    ON knowledge_items(tenant_id, review_status, redaction_status, confidence DESC);

CREATE TABLE IF NOT EXISTS review_jobs (
    job_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    review_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
    requested_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    UNIQUE (tenant_id, review_date)
);

CREATE TABLE IF NOT EXISTS supplier_contracts (
    supplier_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    contract_terms_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (tenant_id, supplier_id)
);

INSERT INTO schema_migrations(version)
VALUES ('2026-08-28-core-v1')
ON CONFLICT(version) DO NOTHING;
