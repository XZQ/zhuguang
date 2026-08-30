CREATE TABLE IF NOT EXISTS audit_archive_manifest (
    archive_id TEXT PRIMARY KEY,
    source_partition TEXT NOT NULL,
    destination_table TEXT NOT NULL,
    archive_month DATE NOT NULL,
    source_rows BIGINT NOT NULL,
    copied_rows BIGINT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('copied', 'verified')),
    copied_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ
);

CREATE OR REPLACE FUNCTION stage_audit_partition_to_foreign(
    source_partition REGCLASS,
    destination_table REGCLASS,
    archive_month DATE
)
RETURNS TABLE(source_rows BIGINT, copied_rows BIGINT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    source_count BIGINT;
    inserted_count BIGINT;
    destination_count BIGINT;
    destination_kind "char";
    archive_key TEXT;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_inherits
        WHERE inhparent = 'audit_log'::REGCLASS
          AND inhrelid = source_partition
    ) THEN
        RAISE EXCEPTION 'source_partition must be a child of audit_log';
    END IF;

    SELECT relkind INTO destination_kind FROM pg_class WHERE oid = destination_table;
    IF destination_kind <> 'f' THEN
        RAISE EXCEPTION 'destination_table must be a provisioned foreign table';
    END IF;

    EXECUTE format('SELECT count(*) FROM %s', source_partition) INTO source_count;
    archive_key := 'archive:' || source_partition::TEXT || ':' || archive_month::TEXT;
    IF EXISTS (SELECT 1 FROM audit_archive_manifest WHERE archive_id = archive_key) THEN
        EXECUTE format(
            'SELECT count(*) FROM %s WHERE created_at >= %L AND created_at < %L',
            destination_table,
            archive_month,
            archive_month + INTERVAL '1 month'
        ) INTO destination_count;
        IF destination_count <> source_count THEN
            RAISE EXCEPTION 'archive verification mismatch: source %, destination %',
                source_count, destination_count;
        END IF;
        UPDATE audit_archive_manifest SET
            source_rows = source_count,
            copied_rows = destination_count,
            status = 'verified',
            verified_at = clock_timestamp()
        WHERE archive_id = archive_key;
        RETURN QUERY SELECT source_count, destination_count;
        RETURN;
    END IF;

    EXECUTE format(
        'INSERT INTO %s SELECT * FROM %s WHERE created_at >= %L AND created_at < %L',
        destination_table,
        source_partition,
        archive_month,
        archive_month + INTERVAL '1 month'
    );
    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    EXECUTE format(
        'SELECT count(*) FROM %s WHERE created_at >= %L AND created_at < %L',
        destination_table,
        archive_month,
        archive_month + INTERVAL '1 month'
    ) INTO destination_count;
    IF inserted_count <> source_count OR destination_count <> source_count THEN
        RAISE EXCEPTION
            'archive copy mismatch: source %, inserted %, destination %',
            source_count, inserted_count, destination_count;
    END IF;

    INSERT INTO audit_archive_manifest(
        archive_id, source_partition, destination_table, archive_month,
        source_rows, copied_rows, status, copied_at, verified_at
    ) VALUES(
        archive_key, source_partition::TEXT, destination_table::TEXT, archive_month,
        source_count, destination_count, 'verified', clock_timestamp(), clock_timestamp()
    )
    ON CONFLICT(archive_id) DO UPDATE SET
        destination_table = excluded.destination_table,
        source_rows = excluded.source_rows,
        copied_rows = excluded.copied_rows,
        status = excluded.status,
        copied_at = excluded.copied_at,
        verified_at = clock_timestamp();

    RETURN QUERY SELECT source_count, destination_count;
END;
$$;

REVOKE ALL ON FUNCTION stage_audit_partition_to_foreign(REGCLASS, REGCLASS, DATE)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION stage_audit_partition_to_foreign(REGCLASS, REGCLASS, DATE)
    TO dianxun_hq;

INSERT INTO schema_migrations(version)
VALUES ('2026-08-28-archive-v1')
ON CONFLICT(version) DO NOTHING;
