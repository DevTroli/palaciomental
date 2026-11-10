from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listaEspera', '0026_identidade_tema_flexivel'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberprofile',
            name='avatar',
            field=models.FileField(blank=True, upload_to='avatars/', verbose_name='Foto de perfil'),
        ),
    ]
