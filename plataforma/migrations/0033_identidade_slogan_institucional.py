from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listaEspera", "0032_identidade_contatos_rodape"),
    ]

    operations = [
        migrations.AddField(
            model_name="identidadeorganizacao",
            name="slogan",
            field=models.CharField(blank=True, max_length=160, verbose_name="Slogan institucional"),
        ),
    ]
