-- Uma concessão temporária impede que várias instâncias processem o mesmo ciclo.
ALTER TABLE guardiao.link_check ADD COLUMN lease_id UUID;
ALTER TABLE guardiao.link_check ADD COLUMN lease_until TIMESTAMPTZ;
ALTER TABLE guardiao.link_check ADD CONSTRAINT lease_consistent
  CHECK ((lease_id IS NULL) = (lease_until IS NULL));
