from django.db import migrations, models
from django.db.models.functions import Lower

class Migration(migrations.Migration):
    dependencies = [("listaEspera", "0006_remove_project_collaboration_tags")]
    operations = [migrations.AddConstraint(model_name="project", constraint=models.UniqueConstraint(Lower("title"), "owner", name="unique_owner_project_title_ci"))]
