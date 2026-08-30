CREATE EXTENSION IF NOT EXISTS pg_cron;

SELECT cron.unschedule(jobid)
FROM cron.job
WHERE jobname IN ('dianxun-nightly-review-enqueue', 'dianxun-audit-partition-maintenance');

SELECT cron.schedule(
    'dianxun-nightly-review-enqueue',
    '0 23 * * *',
    $$
    INSERT INTO review_jobs(job_id, tenant_id, review_date, status, requested_at)
    SELECT
        'review:' || tenant_id || ':' || CURRENT_DATE::TEXT,
        tenant_id,
        CURRENT_DATE,
        'pending',
        clock_timestamp()
    FROM (SELECT DISTINCT tenant_id FROM stores) tenants
    ON CONFLICT(tenant_id, review_date) DO NOTHING
    $$
);

SELECT cron.schedule(
    'dianxun-audit-partition-maintenance',
    '15 0 20 * *',
    $$SELECT ensure_audit_partition(
        (date_trunc('month', CURRENT_DATE) + INTERVAL '1 month')::DATE
    )$$
);

CREATE OR REPLACE VIEW dianxun_cron_health AS
SELECT
    job.jobname,
    details.runid,
    details.status,
    details.return_message,
    details.start_time,
    details.end_time
FROM cron.job_run_details AS details
JOIN cron.job AS job ON job.jobid = details.jobid
WHERE job.jobname IN (
    'dianxun-nightly-review-enqueue',
    'dianxun-audit-partition-maintenance'
);

REVOKE ALL ON dianxun_cron_health FROM PUBLIC;
GRANT SELECT ON dianxun_cron_health TO dianxun_hq;

INSERT INTO schema_migrations(version)
VALUES ('2026-08-28-cron-v1')
ON CONFLICT(version) DO NOTHING;
