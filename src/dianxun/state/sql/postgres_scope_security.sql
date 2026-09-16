-- Applied inside the scope-v2 upgrade transaction, after the security profile.
ALTER TABLE scope_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE scope_revisions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS scope_revision_scope ON scope_revisions;
CREATE POLICY scope_revision_scope ON scope_revisions USING (
    dianxun_tenant_allowed(tenant_id) AND dianxun_store_allowed(store_id)
    AND EXISTS (
        SELECT 1 FROM incidents i WHERE i.incident_id = scope_revisions.incident_id
        AND i.tenant_id = scope_revisions.tenant_id AND i.store_id = scope_revisions.store_id
    )
);

ALTER TABLE batch_lineage ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_lineage FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS batch_lineage_scope ON batch_lineage;
CREATE POLICY batch_lineage_scope ON batch_lineage USING (
    dianxun_tenant_allowed(tenant_id) AND dianxun_store_allowed(store_id)
    AND EXISTS (
        SELECT 1 FROM stores s
        JOIN inventory_batches p ON p.store_id = s.store_id
        JOIN inventory_batches c ON c.store_id = s.store_id
        WHERE s.tenant_id = batch_lineage.tenant_id AND s.store_id = batch_lineage.store_id
        AND p.batch_id = batch_lineage.parent_batch_id
        AND c.batch_id = batch_lineage.child_batch_id
    )
);

REVOKE ALL ON scope_revisions, batch_lineage FROM PUBLIC, dianxun_business_ro;
REVOKE ALL ON scope_revisions, batch_lineage FROM dianxun_runtime, dianxun_hq;
GRANT SELECT, INSERT ON scope_revisions, batch_lineage TO dianxun_runtime, dianxun_hq;
