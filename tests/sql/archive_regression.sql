-- Run with psql -X -v ON_ERROR_STOP=1, after core/security/archive profiles.
-- Destructive fixture reset: ONLY a dedicated zhuguang_archive_test database.
DO $$
BEGIN
    IF current_database() <> 'zhuguang_archive_test' THEN
        RAISE EXCEPTION 'requires dedicated zhuguang_archive_test database';
    END IF;
END;
$$;

CREATE EXTENSION IF NOT EXISTS postgres_fdw;
CREATE SCHEMA IF NOT EXISTS archive_fixture;
CREATE TABLE IF NOT EXISTS archive_fixture.sink (LIKE public.audit_log);
CREATE TABLE IF NOT EXISTS archive_fixture.other_sink (LIKE public.audit_log);
DROP TRIGGER IF EXISTS corrupt_insert ON archive_fixture.sink;
CREATE SERVER IF NOT EXISTS archive_fixture_server FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host '/var/run/postgresql', dbname 'zhuguang_archive_test');
CREATE USER MAPPING IF NOT EXISTS FOR CURRENT_USER SERVER archive_fixture_server
    OPTIONS (user 'postgres');
DROP FOREIGN TABLE IF EXISTS public.sink, public.other_sink;
IMPORT FOREIGN SCHEMA archive_fixture LIMIT TO (sink, other_sink)
    FROM SERVER archive_fixture_server INTO public;
TRUNCATE public.audit_log, public.audit_archive_manifest,
    archive_fixture.sink, archive_fixture.other_sink;
INSERT INTO public.audit_log (
    audit_id, request_id, tenant_id, actor, tool_name,
    request_json, response_json, created_at
) VALUES (
    'archive-test-1', 'archive-request-1', 'demo', 'Auditor', 'outcome_verify',
    '{"batch":"one","nested":{"safe":false}}', '{"accepted":false}',
    date_trunc('month', CURRENT_DATE) + INTERVAL '1 day'
);

-- Initial copy and idempotent retry must both succeed without duplicates.
DO $$
DECLARE
    month_start DATE := date_trunc('month', CURRENT_DATE)::DATE;
    source REGCLASS := ('public.audit_log_' || to_char(CURRENT_DATE, 'YYYYMM'))::REGCLASS;
    result RECORD;
BEGIN
    SELECT * INTO result FROM stage_audit_partition_to_foreign(source, 'public.sink', month_start);
    IF result.source_rows <> 1 OR result.copied_rows <> 1 THEN
        RAISE EXCEPTION 'initial copy returned wrong counts';
    END IF;
    SELECT * INTO result FROM stage_audit_partition_to_foreign(source, 'public.sink', month_start);
    IF result.source_rows <> 1 OR result.copied_rows <> 1 THEN
        RAISE EXCEPTION 'retry duplicated rows';
    END IF;
END;
$$;

-- A count-preserving modification must never be certified as verified.
UPDATE archive_fixture.sink SET response_json = '{"accepted":true}';
DO $$
DECLARE
    month_start DATE := date_trunc('month', CURRENT_DATE)::DATE;
    source REGCLASS := ('public.audit_log_' || to_char(CURRENT_DATE, 'YYYYMM'))::REGCLASS;
BEGIN
    BEGIN
        PERFORM stage_audit_partition_to_foreign(source, 'public.sink', month_start);
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'archive content mismatch%' THEN
            RETURN;
        END IF;
        RAISE;
    END;
    RAISE EXCEPTION 'REGRESSION: equal-count tampering was accepted';
END;
$$;
UPDATE archive_fixture.sink SET response_json = '{"accepted":false}';

-- A different destination may contain identical data but is not the old receipt.
INSERT INTO archive_fixture.other_sink SELECT * FROM archive_fixture.sink;
DO $$
DECLARE
    month_start DATE := date_trunc('month', CURRENT_DATE)::DATE;
    source REGCLASS := ('public.audit_log_' || to_char(CURRENT_DATE, 'YYYYMM'))::REGCLASS;
BEGIN
    BEGIN
        PERFORM stage_audit_partition_to_foreign(source, 'public.other_sink', month_start);
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'archive destination mismatch%' THEN
            RETURN;
        END IF;
        RAISE;
    END;
    RAISE EXCEPTION 'REGRESSION: existing receipt accepted a different destination';
END;
$$;

-- Missing rows must be rejected too; source data must survive every check.
DELETE FROM archive_fixture.sink;
DO $$
DECLARE
    month_start DATE := date_trunc('month', CURRENT_DATE)::DATE;
    source REGCLASS := ('public.audit_log_' || to_char(CURRENT_DATE, 'YYYYMM'))::REGCLASS;
BEGIN
    BEGIN
        PERFORM stage_audit_partition_to_foreign(source, 'public.sink', month_start);
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'archive verification mismatch%' THEN
            IF (SELECT count(*) FROM public.audit_log) <> 1 THEN
                RAISE EXCEPTION 'source data changed';
            END IF;
            RETURN;
        END IF;
        RAISE;
    END;
    RAISE EXCEPTION 'REGRESSION: missing row was accepted';
END;
$$;
-- A destination-side transformation on the first copy must roll back the receipt.
TRUNCATE public.audit_archive_manifest, archive_fixture.sink;
CREATE OR REPLACE FUNCTION archive_fixture.corrupt_insert()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.response_json := '{"accepted":true}';
    RETURN NEW;
END;
$$;
CREATE TRIGGER corrupt_insert BEFORE INSERT ON archive_fixture.sink
    FOR EACH ROW EXECUTE FUNCTION archive_fixture.corrupt_insert();
DO $$
DECLARE
    month_start DATE := date_trunc('month', CURRENT_DATE)::DATE;
    source REGCLASS := ('public.audit_log_' || to_char(CURRENT_DATE, 'YYYYMM'))::REGCLASS;
BEGIN
    BEGIN
        PERFORM stage_audit_partition_to_foreign(source, 'public.sink', month_start);
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'archive content mismatch%' THEN
            IF EXISTS (SELECT 1 FROM public.audit_archive_manifest) THEN
                RAISE EXCEPTION 'failed copy left a verified receipt';
            END IF;
            RETURN;
        END IF;
        RAISE;
    END;
    RAISE EXCEPTION 'REGRESSION: initial copy accepted destination transformation';
END;
$$;
DROP TRIGGER corrupt_insert ON archive_fixture.sink;
DO $$
BEGIN
    IF (SELECT count(*) FROM public.audit_log) <> 1
       OR EXISTS (SELECT 1 FROM archive_fixture.sink)
       OR EXISTS (SELECT 1 FROM public.audit_archive_manifest) THEN
        RAISE EXCEPTION 'failed archive did not preserve source and roll back copy/receipt';
    END IF;
END;
$$;
SELECT 'archive regression passed' AS result;
