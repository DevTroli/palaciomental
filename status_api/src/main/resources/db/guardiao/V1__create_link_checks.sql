-- Schema e histórico Flyway pertencem ao serviço, não às migrations Django.
CREATE TABLE guardiao.link_check (
    link_id BIGINT PRIMARY KEY CHECK (link_id > 0),
    url TEXT NOT NULL CHECK (char_length(url) BETWEEN 1 AND 500),
    status VARCHAR(24) CHECK (status IN ('ACESSIVEL', 'REDIRECIONADO', 'REQUER_LOGIN', 'QUEBRADO', 'SEM_RESPOSTA')),
    checked_at TIMESTAMPTZ,
    failed_cycles SMALLINT NOT NULL DEFAULT 0 CHECK (failed_cycles BETWEEN 0 AND 3),
    next_check_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT checked_status_consistent CHECK ((status IS NULL) = (checked_at IS NULL))
);

CREATE INDEX link_check_next_check_idx ON guardiao.link_check (next_check_at, link_id);
