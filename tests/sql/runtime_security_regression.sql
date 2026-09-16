-- Actual separate database login; only run inside the network-isolated test container.
-- The fixture reset is forbidden in any other database.
\set ON_ERROR_STOP on
DO $$
BEGIN
    IF current_database() <> 'zhuguang_runtime_test' THEN
        RAISE EXCEPTION 'requires dedicated zhuguang_runtime_test database';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'zhuguang_test_runtime') THEN
        CREATE ROLE zhuguang_test_runtime LOGIN NOSUPERUSER NOCREATEDB
            NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    IF EXISTS (
        SELECT FROM pg_roles WHERE rolname = 'zhuguang_test_runtime'
          AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
    ) THEN
        RAISE EXCEPTION 'test runtime login must not be privileged';
    END IF;
END;
$$;
GRANT dianxun_runtime TO zhuguang_test_runtime;
INSERT INTO dianxun_principal_scope(database_role, tenant_id, runtime_role, store_id)
VALUES ('zhuguang_test_runtime', 'scope-a', 'runtime', 'S03')
ON CONFLICT(database_role) DO UPDATE SET
    tenant_id = excluded.tenant_id, runtime_role = excluded.runtime_role,
    store_id = excluded.store_id;
TRUNCATE stores CASCADE;
TRUNCATE audit_log, runtime_contexts;
INSERT INTO stores VALUES
    ('S03', 'scope-a', 'synthetic own store', 'UTC'),
    ('S04', 'scope-a', 'synthetic other store', 'UTC'),
    ('S05', 'scope-b', 'synthetic other tenant', 'UTC');
INSERT INTO devices VALUES
    ('D03', 'S03', 'test', 'normal', 'closed', 'on', 'on', 20, now()),
    ('D04', 'S04', 'test', 'normal', 'closed', 'on', 'on', 20, now());
INSERT INTO audit_log (
    audit_id, request_id, tenant_id, actor, tool_name, request_json, response_json, created_at
) VALUES ('runtime-audit-1', 'runtime-request-1', 'scope-a', 'Executor', 'test', '{}', '{}', now());

-- Real new connection, not SET ROLE in a superuser session.
\connect zhuguang_runtime_test zhuguang_test_runtime 127.0.0.1
DO $$
DECLARE
    affected INTEGER;
    statement TEXT;
BEGIN
    IF current_user <> 'zhuguang_test_runtime' OR session_user <> 'zhuguang_test_runtime' THEN
        RAISE EXCEPTION 'expected a separate runtime login';
    END IF;
    -- Untrusted client settings must never expand the registered login scope.
    PERFORM set_config('dianxun.tenant_id', '*', false);
    PERFORM set_config('dianxun.runtime_role', 'hq', false);
    PERFORM set_config('dianxun.store_id', 'S04', false);
    IF (SELECT array_agg(store_id ORDER BY store_id) FROM stores) <> ARRAY['S03']::TEXT[] THEN
        RAISE EXCEPTION 'REGRESSION: runtime store scope escaped';
    END IF;
    UPDATE devices SET health_state = 'fault' WHERE device_id = 'D03';
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 1 THEN
        RAISE EXCEPTION 'allowed runtime update did not write exactly one row';
    END IF;
    UPDATE devices SET health_state = 'fault' WHERE device_id = 'D04';
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 0 THEN
        RAISE EXCEPTION 'REGRESSION: runtime wrote another store';
    END IF;
    INSERT INTO runtime_contexts VALUES ('scope-a', 'task-own', 'S03', 1, '{}');
    INSERT INTO audit_log (
        audit_id, request_id, tenant_id, actor, tool_name, request_json, response_json, created_at
    ) VALUES ('runtime-audit-2', 'runtime-request-2', 'scope-a', 'Executor', 'test', '{}', '{}', now());
    IF (SELECT count(*) FROM audit_log) <> 2 THEN
        RAISE EXCEPTION 'runtime audit append/read did not work';
    END IF;
    FOREACH statement IN ARRAY ARRAY[
        'UPDATE audit_log SET actor = ''tampered'' WHERE audit_id = ''runtime-audit-1''',
        'DELETE FROM audit_log WHERE audit_id = ''runtime-audit-1''',
        'TRUNCATE audit_log',
        'UPDATE dianxun_principal_scope SET runtime_role = ''hq''',
        'SELECT supplier_id FROM supplier_contracts',
        'INSERT INTO stores VALUES (''S06'', ''scope-b'', ''forbidden'', ''UTC'')',
        'INSERT INTO runtime_contexts VALUES (''scope-a'', ''task-other'', ''S04'', 1, ''{}'')',
        'INSERT INTO runtime_contexts VALUES (''scope-b'', ''task-tenant'', ''S03'', 1, ''{}'')'
    ] LOOP
        BEGIN
            EXECUTE statement;
        EXCEPTION WHEN insufficient_privilege THEN
            CONTINUE;
        END;
        RAISE EXCEPTION 'REGRESSION: runtime accepted forbidden statement: %', statement;
    END LOOP;
END;
$$;
\connect zhuguang_runtime_test postgres 127.0.0.1
DO $$
BEGIN
    IF (SELECT health_state FROM devices WHERE device_id = 'D04') <> 'normal'
       OR (SELECT count(*) FROM audit_log WHERE actor = 'Executor') <> 2
       OR (SELECT count(*) FROM runtime_contexts) <> 1 THEN
        RAISE EXCEPTION 'administrator reconciliation failed';
    END IF;
END;
$$;
SELECT 'RUNTIME_SECURITY_REGRESSION_OK' AS result;
