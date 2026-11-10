import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("listaEspera", "0033_identidade_slogan_institucional")]

    operations = [
        migrations.AddField(
            model_name="identidadeorganizacao",
            name="site_oficial",
            field=models.URLField(blank=True, max_length=500, validators=[django.core.validators.URLValidator(schemes=["http", "https"])], verbose_name="Site oficial"),
        ),
    ]
