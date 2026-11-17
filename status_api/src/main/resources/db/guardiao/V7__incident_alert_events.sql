-- Eventos persistem junto às transições; cada canal controla sua própria entrega.
ALTER TABLE guardiao.service_incidents ADD COLUMN tenant_host TEXT;

CREATE TABLE guardiao.incident_alert_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id BIGINT NOT NULL REFERENCES guardiao.service_incidents(id),
    event_type TEXT NOT NULL CHECK (event_type IN ('opened', 'recovered', 'public', 'severe', 'extended')),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (incident_id, event_type)
);

CREATE TABLE guardiao.incident_alert_deliveries (
    event_id BIGINT NOT NULL REFERENCES guardiao.incident_alert_events(id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK (channel IN ('discord', 'email', 'inbox')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'expired')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    next_attempt_at TIMESTAMPTZ NOT NULL,
    last_error TEXT,
    sent_at TIMESTAMPTZ,
    PRIMARY KEY (event_id, channel)
);

CREATE INDEX incident_alert_deliveries_due ON guardiao.incident_alert_deliveries (channel, next_attempt_at)
    WHERE status = 'pending';
