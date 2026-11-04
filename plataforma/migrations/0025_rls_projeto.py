"""RLS mínima: isolamento de projetos por escopo no PostgreSQL.

Segunda barreira, depois dos querysets escopados da aplicação. Ver
docs/arquitetura-multi-tenant-rls.md.
"""

from django.db import migrations

TABLE = '"listaEspera_project"'

POLICY_EXPR = """
    coalesce(current_setting('app.rls_mode', true), '') = 'system'
    OR (coalesce(current_setting('app.rls_mode', true), '') = 'global'
        AND organizacao_id IS NULL)
    OR (coalesce(current_setting('app.rls_mode', true), '') = 'tenant'
        AND organizacao_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
"""

FORWARD = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY pm_projeto_escopo ON {TABLE}
    FOR ALL
    USING ({POLICY_EXPR})
    WITH CHECK ({POLICY_EXPR});
"""

BACKWARD = f"""
DROP POLICY IF EXISTS pm_projeto_escopo ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FORWARD)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(BACKWARD)


class Migration(migrations.Migration):
    dependencies = [("listaEspera", "0024_vinculoprojetoinstitucional_orientador")]
    operations = [migrations.RunPython(forwards, backwards)]
