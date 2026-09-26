from collections import defaultdict

from django.db import migrations, models
from django.db.models.functions import Lower


def resolve_duplicate_titles(apps, schema_editor):
    Project = apps.get_model("listaEspera", "Project")
    projects = Project.objects.order_by("owner_id", "pk").only("pk", "owner_id", "title")
    used_titles = defaultdict(set)

    for project in projects:
        original = (project.title or "Projeto").strip() or "Projeto"
        normalized = original.casefold()
        owner_titles = used_titles[project.owner_id]

        if normalized not in owner_titles:
            owner_titles.add(normalized)
            if original != project.title:
                project.title = original
                project.save(update_fields=["title"])
            continue

        number = 2
        while True:
            suffix = f" ({number})"
            candidate = f"{original[:140 - len(suffix)]}{suffix}"
            candidate_normalized = candidate.casefold()
            if candidate_normalized not in owner_titles:
                project.title = candidate
                project.save(update_fields=["title"])
                owner_titles.add(candidate_normalized)
                break
            number += 1


class Migration(migrations.Migration):
    dependencies = [("listaEspera", "0006_remove_project_collaboration_tags")]

    operations = [
        migrations.RunPython(resolve_duplicate_titles, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.UniqueConstraint(
                Lower("title"),
                "owner",
                name="unique_owner_project_title_ci",
            ),
        ),
    ]
