CREATE TABLE guardiao.service_journeys (
    journey TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL
);

INSERT INTO guardiao.service_journeys (journey, started_at)
SELECT journey, min(occurred_at)
FROM (
    SELECT journey, checked_at AS occurred_at FROM guardiao.service_checks
    UNION ALL
    SELECT journey, started_at AS occurred_at FROM guardiao.service_incidents
) AS history
GROUP BY journey
ON CONFLICT (journey) DO NOTHING;
