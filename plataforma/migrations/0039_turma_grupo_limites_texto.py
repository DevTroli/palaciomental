from django.db import migrations, models
from django.db.models.functions import Length


def validar_limites_existentes(apps, schema_editor):
    Turma = apps.get_model("plataforma", "Turma")
    Grupo = apps.get_model("plataforma", "Grupo")
    using = schema_editor.connection.alias
    excedentes = (
        Turma.objects.using(using).annotate(tamanho=Length("nome")).filter(tamanho__gt=80).exists()
        or Turma.objects.using(using).annotate(tamanho=Length("descricao")).filter(tamanho__gt=280).exists()
        or Grupo.objects.using(using).annotate(tamanho=Length("nome")).filter(tamanho__gt=80).exists()
    )
    if excedentes:
        raise RuntimeError("Há nomes ou descrições acima dos novos limites. Revise esses registros antes de migrar; nenhum texto será cortado automaticamente.")


class Migration(migrations.Migration):
    dependencies = [
        ("plataforma", "0038_projectlink_descricao_projectlink_turma_and_more"),
    ]

    operations = [
        migrations.RunPython(validar_limites_existentes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="turma",
            name="nome",
            field=models.CharField(max_length=80, verbose_name="Nome"),
        ),
        migrations.AlterField(
            model_name="turma",
            name="descricao",
            field=models.TextField(blank=True, max_length=280, verbose_name="Descrição"),
        ),
        migrations.AlterField(
            model_name="grupo",
            name="nome",
            field=models.CharField(max_length=80, verbose_name="Nome"),
        ),
    ]
