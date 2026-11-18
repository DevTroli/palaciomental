ALTER TABLE guardiao.monitored_tenants
    ADD COLUMN slug VARCHAR(80),
    ADD COLUMN display_name VARCHAR(160);

CREATE UNIQUE INDEX monitored_tenants_slug_unique
    ON guardiao.monitored_tenants (slug)
    WHERE slug IS NOT NULL;
