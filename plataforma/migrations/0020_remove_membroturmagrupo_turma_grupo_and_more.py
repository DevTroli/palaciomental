import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listaEspera", "0019_migrar_turma_grupo_legado"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name="ConviteTurmaGrupo"),
        migrations.DeleteModel(name="MembroTurmaGrupo"),
        migrations.DeleteModel(name="ProjetoTurmaGrupo"),
        migrations.DeleteModel(name="TurmaGrupo"),
        migrations.CreateModel(
            name="ConviteGrupo",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254, verbose_name="E-mail convidado")),
                ("papel", models.CharField(choices=[("membro", "Membro")], default="membro", max_length=20, verbose_name="Papel local")),
                ("hash_token", models.CharField(max_length=64, unique=True, verbose_name="Hash do token")),
                ("status", models.CharField(choices=[("pendente", "Pendente"), ("aceito", "Aceito"), ("revogado", "Revogado")], default="pendente", max_length=20, verbose_name="Status")),
                ("expira_em", models.DateTimeField(verbose_name="Expira em")),
                ("aceito_em", models.DateTimeField(blank=True, null=True, verbose_name="Aceito em")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("convidado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="convites_grupo_emitidos", to=settings.AUTH_USER_MODEL, verbose_name="Convidado por")),
                ("grupo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="convites", to="listaEspera.grupo", verbose_name="Grupo")),
            ],
            options={"verbose_name": "Convite de grupo", "verbose_name_plural": "Convites de grupos"},
        ),
        migrations.AddIndex(model_name="convitegrupo", index=models.Index(fields=["grupo", "status"], name="listaEspera_grupo_i_8c5a8d_idx")),
        migrations.AddIndex(model_name="convitegrupo", index=models.Index(fields=["email", "status"], name="listaEspera_email_4f448c_idx")),
    ]
