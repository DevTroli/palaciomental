from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("plataforma", "0039_turma_grupo_limites_texto")]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="scope_organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name="notifications", to="plataforma.organizacao"),
        ),
        migrations.AddField(
            model_name="notification",
            name="source_key",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(condition=models.Q(source_key__isnull=False),
                                               fields=("recipient", "source_key"),
                                               name="notification_recipient_source_unique"),
        ),
    ]
