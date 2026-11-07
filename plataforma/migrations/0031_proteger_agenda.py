"""A agenda passa a compartilhar a barreira de tenant do PostgreSQL."""
from django.db import migrations


TABLE = '"plataforma_eventocalendario"'
EXPRESSION = """
coalesce(current_setting('app.rls_mode', true), '') = 'system'
OR (coalesce(current_setting('app.rls_mode', true), '') = 'tenant'
    AND organizacao_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(f"""
        ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
        CREATE POLICY pm_agenda_escopo ON {TABLE} FOR ALL
            USING ({EXPRESSION}) WITH CHECK ({EXPRESSION});
        """)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(f"""
        DROP POLICY IF EXISTS pm_agenda_escopo ON {TABLE};
        ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
        """)


class Migration(migrations.Migration):
    dependencies = [
        ("listaEspera", "0030_criar_agenda"),
    ]
    operations = [migrations.RunPython(forwards, backwards)]
