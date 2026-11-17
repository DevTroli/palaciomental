-- Identifica cada ciclo concluído para tornar retentativas idempotentes.
ALTER TABLE guardiao.link_check ADD COLUMN last_cycle_id UUID;
ALTER TABLE guardiao.link_check ADD COLUMN url_revision BIGINT NOT NULL DEFAULT 1 CHECK (url_revision > 0);
