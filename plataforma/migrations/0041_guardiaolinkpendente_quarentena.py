from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("plataforma", "0040_notification_incident_scope")]

    operations = [
        migrations.AddField(
            model_name="guardiaolinkpendente",
            name="quarentena",
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name="guardiaolinkpendente",
            name="rejeicao_http",
            field=models.PositiveSmallIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="guardiaolinkpendente",
            name="rejeitada_em",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
