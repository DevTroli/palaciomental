-- Limite por domínio compartilhado entre instâncias do serviço.
CREATE TABLE guardiao.domain_lease (
    host TEXT PRIMARY KEY CHECK (char_length(host) BETWEEN 1 AND 253),
    lease_id UUID NOT NULL,
    lease_until TIMESTAMPTZ NOT NULL
);
