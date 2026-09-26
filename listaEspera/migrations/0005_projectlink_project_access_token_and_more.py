from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [("listaEspera", "0004_project_collaboration_description_and_more")]
    operations = [
        migrations.AddField(model_name="project", name="access_token", field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        migrations.AddField(model_name="projectmember", name="can_manage_milestones", field=models.BooleanField(default=True, verbose_name="Pode gerenciar marcos")),
        migrations.AlterField(model_name="project", name="visibility", field=models.CharField(choices=[("publico", "Público"), ("restrito", "Restrito — acesso por link"), ("privado", "Privado")], default="privado", max_length=20, verbose_name="Visibilidade")),
        migrations.CreateModel(name="ProjectLink", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("label", models.CharField(max_length=80, verbose_name="Nome do link")),
            ("url", models.URLField(max_length=500, verbose_name="URL")),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="links", to="listaEspera.project")),
        ], options={"ordering": ["created_at"]}),
    ]
