CREATE TABLE guardiao.monitored_tenants (
    organization_id UUID PRIMARY KEY,
    hostname VARCHAR(253) NOT NULL UNIQUE,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
