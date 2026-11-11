-- A limpeza só acontece após receber todos os lotes de um retrato concluído.
ALTER TABLE guardiao.link_check ADD COLUMN snapshot_id UUID;
CREATE TABLE guardiao.sync_snapshot (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    snapshot_id UUID NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);
