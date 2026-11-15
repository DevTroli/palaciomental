CREATE TABLE guardiao.service_checks (
    journey TEXT NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL,
    successful BOOLEAN NOT NULL,
    PRIMARY KEY (journey, checked_at)
);

CREATE TABLE guardiao.service_incidents (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    journey TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    recovered_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX service_incidents_open ON guardiao.service_incidents (journey)
    WHERE recovered_at IS NULL;
