from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("plataforma", "0008_organizacao_alter_collaborationrequest_id_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="WaitlistEntry",
        ),
    ]
