from django.db import migrations


INDEX = "pm_user_email_normalized_unique"


def enforce_unique_email(apps, schema_editor):
    user = apps.get_model("auth", "User")
    table = schema_editor.quote_name(user._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"SELECT count(*) FROM (SELECT lower(trim(email)) FROM {table} "
                       "WHERE trim(email) <> '' GROUP BY lower(trim(email)) HAVING count(*) > 1) duplicates")
        count = cursor.fetchone()[0]
        if count:
            raise RuntimeError(
                f"Migração interrompida: {count} grupos de e-mail duplicado. "
                "Execute verificar_emails e resolva as contas com aprovação antes de repetir."
            )
    schema_editor.execute(f"CREATE UNIQUE INDEX {INDEX} ON {table} (lower(trim(email))) WHERE trim(email) <> ''")


def remove_unique_email(apps, schema_editor):
    schema_editor.execute(f"DROP INDEX {INDEX}")


class Migration(migrations.Migration):
    dependencies = [
        ("plataforma", "0041_guardiaolinkpendente_quarentena"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [migrations.RunPython(enforce_unique_email, remove_unique_email)]
