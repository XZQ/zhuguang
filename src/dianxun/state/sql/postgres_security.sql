DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dianxun_runtime') THEN
        CREATE ROLE dianxun_runtime NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dianxun_business_ro') THEN
        CREATE ROLE dianxun_business_ro NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dianxun_hq') THEN
        CREATE ROLE dianxun_hq NOLOGIN;
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS dianxun_principal_scope (
    database_role TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    runtime_role TEXT NOT NULL CHECK (runtime_role IN ('runtime', 'hq')),
    store_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

INSERT INTO dianxun_principal_scope(database_role, tenant_id, runtime_role, store_id)
VALUES (session_user::TEXT, '*', 'hq', NULL)
ON CONFLICT(database_role) DO NOTHING;

CREATE OR REPLACE FUNCTION dianxun_current_scope()
RETURNS TABLE(tenant_id TEXT, runtime_role TEXT, store_id TEXT)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT principal.tenant_id, principal.runtime_role, principal.store_id
    FROM public.dianxun_principal_scope principal
    WHERE principal.database_role = session_user::TEXT;
$$;

CREATE OR REPLACE FUNCTION dianxun_is_hq()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.dianxun_principal_scope principal
        WHERE principal.database_role = session_user::TEXT
          AND principal.runtime_role = 'hq'
    );
$$;

CREATE OR REPLACE FUNCTION dianxun_tenant_allowed(row_tenant TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.dianxun_principal_scope principal
        WHERE principal.database_role = session_user::TEXT
          AND (principal.tenant_id = '*' OR principal.tenant_id = row_tenant)
    );
$$;

CREATE OR REPLACE FUNCTION dianxun_store_allowed(row_store TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.dianxun_principal_scope principal
        WHERE principal.database_role = session_user::TEXT
          AND (
              principal.runtime_role = 'hq'
              OR principal.store_id IS NULL
              OR principal.store_id = row_store
          )
    );
$$;

ALTER TABLE stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE stores FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS stores_scope ON stores;
CREATE POLICY stores_scope ON stores
    USING (dianxun_tenant_allowed(tenant_id) AND dianxun_store_allowed(store_id))
    WITH CHECK (dianxun_tenant_allowed(tenant_id) AND dianxun_store_allowed(store_id));

ALTER TABLE devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE devices FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS devices_scope ON devices;
CREATE POLICY devices_scope ON devices
    USING (EXISTS (
        SELECT 1 FROM stores s
        WHERE s.store_id = devices.store_id
          AND dianxun_tenant_allowed(s.tenant_id)
          AND dianxun_store_allowed(s.store_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM stores s
        WHERE s.store_id = devices.store_id
          AND dianxun_tenant_allowed(s.tenant_id)
          AND dianxun_store_allowed(s.store_id)
    ));

ALTER TABLE device_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_readings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS readings_scope ON device_readings;
CREATE POLICY readings_scope ON device_readings
    USING (EXISTS (
        SELECT 1 FROM devices d JOIN stores s ON s.store_id = d.store_id
        WHERE d.device_id = device_readings.device_id
          AND dianxun_tenant_allowed(s.tenant_id)
          AND dianxun_store_allowed(s.store_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM devices d JOIN stores s ON s.store_id = d.store_id
        WHERE d.device_id = device_readings.device_id
          AND dianxun_tenant_allowed(s.tenant_id)
          AND dianxun_store_allowed(s.store_id)
    ));

ALTER TABLE inventory_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_batches FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS batches_scope ON inventory_batches;
CREATE POLICY batches_scope ON inventory_batches
    USING (EXISTS (
        SELECT 1 FROM stores s
        WHERE s.store_id = inventory_batches.store_id
          AND dianxun_tenant_allowed(s.tenant_id)
          AND dianxun_store_allowed(s.store_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM stores s
        WHERE s.store_id = inventory_batches.store_id
          AND dianxun_tenant_allowed(s.tenant_id)
          AND dianxun_store_allowed(s.store_id)
    ));

ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS incidents_scope ON incidents;
CREATE POLICY incidents_scope ON incidents
    USING (dianxun_tenant_allowed(tenant_id) AND dianxun_store_allowed(store_id))
    WITH CHECK (dianxun_tenant_allowed(tenant_id) AND dianxun_store_allowed(store_id));

ALTER TABLE sales_holds ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales_holds FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS holds_scope ON sales_holds;
CREATE POLICY holds_scope ON sales_holds
    USING (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = sales_holds.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = sales_holds.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ));

ALTER TABLE workorders ENABLE ROW LEVEL SECURITY;
ALTER TABLE workorders FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS workorders_scope ON workorders;
CREATE POLICY workorders_scope ON workorders
    USING (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = workorders.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = workorders.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ));

ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS approvals_scope ON approvals;
CREATE POLICY approvals_scope ON approvals
    USING (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = approvals.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = approvals.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ));

ALTER TABLE actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE actions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS actions_scope ON actions;
CREATE POLICY actions_scope ON actions
    USING (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = actions.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = actions.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ));

ALTER TABLE verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE verifications FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS verifications_scope ON verifications;
CREATE POLICY verifications_scope ON verifications
    USING (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = verifications.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = verifications.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ));

ALTER TABLE manual_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE manual_evidence FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS manual_evidence_scope ON manual_evidence;
CREATE POLICY manual_evidence_scope ON manual_evidence
    USING (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = manual_evidence.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM incidents i
        WHERE i.incident_id = manual_evidence.incident_id
          AND dianxun_tenant_allowed(i.tenant_id)
          AND dianxun_store_allowed(i.store_id)
    ));

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS audit_scope ON audit_log;
CREATE POLICY audit_scope ON audit_log
    USING (dianxun_tenant_allowed(tenant_id))
    WITH CHECK (dianxun_tenant_allowed(tenant_id));

SELECT ensure_audit_partition(date_trunc('month', CURRENT_DATE)::DATE);
SELECT ensure_audit_partition((date_trunc('month', CURRENT_DATE) + INTERVAL '1 month')::DATE);

ALTER TABLE idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS idempotency_scope ON idempotency;
CREATE POLICY idempotency_scope ON idempotency
    USING (dianxun_tenant_allowed(tenant_id))
    WITH CHECK (dianxun_tenant_allowed(tenant_id));

ALTER TABLE knowledge_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS knowledge_scope ON knowledge_items;
CREATE POLICY knowledge_scope ON knowledge_items
    USING (dianxun_tenant_allowed(tenant_id))
    WITH CHECK (dianxun_tenant_allowed(tenant_id));

ALTER TABLE review_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_jobs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS review_jobs_scope ON review_jobs;
CREATE POLICY review_jobs_scope ON review_jobs
    USING (dianxun_tenant_allowed(tenant_id))
    WITH CHECK (dianxun_tenant_allowed(tenant_id));

ALTER TABLE supplier_contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE supplier_contracts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS supplier_hq_only ON supplier_contracts;
CREATE POLICY supplier_hq_only ON supplier_contracts
    USING (
        dianxun_is_hq()
        AND dianxun_tenant_allowed(tenant_id)
    )
    WITH CHECK (
        dianxun_is_hq()
        AND dianxun_tenant_allowed(tenant_id)
    );

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON dianxun_principal_scope
    FROM dianxun_runtime, dianxun_business_ro, dianxun_hq;
GRANT USAGE ON SCHEMA public TO dianxun_runtime, dianxun_business_ro, dianxun_hq;
GRANT SELECT, INSERT, UPDATE ON
    meta, stores, devices, device_readings, inventory_batches, sales_holds,
    approvals, workorders, manual_evidence, incidents, actions, verifications,
    audit_log, idempotency, knowledge_items, review_jobs
    TO dianxun_runtime;
GRANT SELECT, UPDATE ON tool_failures TO dianxun_runtime;
GRANT SELECT ON stores, devices, device_readings, inventory_batches, workorders
    TO dianxun_business_ro;
GRANT dianxun_runtime TO dianxun_hq;
GRANT INSERT ON tool_failures TO dianxun_hq;
GRANT SELECT, INSERT, UPDATE ON supplier_contracts TO dianxun_hq;
REVOKE ALL ON FUNCTION dianxun_current_scope() FROM PUBLIC;
REVOKE ALL ON FUNCTION dianxun_is_hq() FROM PUBLIC;
REVOKE ALL ON FUNCTION dianxun_tenant_allowed(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION dianxun_store_allowed(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION dianxun_current_scope()
    TO dianxun_runtime, dianxun_business_ro;
GRANT EXECUTE ON FUNCTION dianxun_is_hq() TO dianxun_runtime, dianxun_business_ro;
GRANT EXECUTE ON FUNCTION dianxun_tenant_allowed(TEXT)
    TO dianxun_runtime, dianxun_business_ro;
GRANT EXECUTE ON FUNCTION dianxun_store_allowed(TEXT)
    TO dianxun_runtime, dianxun_business_ro;
GRANT EXECUTE ON FUNCTION ensure_audit_partition(DATE) TO dianxun_runtime;

INSERT INTO schema_migrations(version)
VALUES ('2026-08-28-security-v2')
ON CONFLICT(version) DO NOTHING;
