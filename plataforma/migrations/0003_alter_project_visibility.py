from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listaEspera", "0002_memberprofile_project_projectmember_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="visibility",
            field=models.CharField(
                verbose_name="Visibilidade",
                choices=[("publico", "Público"), ("privado", "Privado")],
                default="privado",
                max_length=20,
            ),
        ),
    ]
