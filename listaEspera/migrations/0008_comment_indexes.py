from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listaEspera", "0007_unique_owner_project_title_ci"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="projectcomment",
            index=models.Index(
                fields=["project", "created_at"],
                name="comment_project_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="projectcomment",
            index=models.Index(
                fields=["parent", "created_at"],
                name="comment_parent_date_idx",
            ),
        ),
    ]
