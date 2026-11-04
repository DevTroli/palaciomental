from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [("listaEspera", "0005_projectlink_project_access_token_and_more")]
    operations = [migrations.RemoveField(model_name="project", name="collaboration_tags")]
