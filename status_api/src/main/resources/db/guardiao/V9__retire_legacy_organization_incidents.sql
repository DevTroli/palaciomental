ALTER TABLE guardiao.service_incidents ADD COLUMN retired_at TIMESTAMPTZ;

-- A jornada antiga deixou de ser coletada; retirada não equivale a recuperação.
UPDATE guardiao.service_incidents
SET retired_at = now()
WHERE journey = 'organizacao' AND recovered_at IS NULL;

UPDATE guardiao.incident_alert_deliveries d
SET status = 'expired', last_error = 'JOURNEY_RETIRED'
FROM guardiao.incident_alert_events e
JOIN guardiao.service_incidents i ON i.id = e.incident_id
WHERE d.event_id = e.id AND i.retired_at IS NOT NULL AND d.status = 'pending';
