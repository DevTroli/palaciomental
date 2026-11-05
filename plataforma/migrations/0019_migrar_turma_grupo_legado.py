from django.db import migrations
from django.utils import timezone


def nome_disponivel(queryset, nome, campo="nome"):
    base = nome[:150]
    candidato = base
    contador = 2
    while queryset.filter(**{campo: candidato}).exists():
        sufixo = f" ({contador})"
        candidato = f"{base[:160 - len(sufixo)]}{sufixo}"
        contador += 1
    return candidato


def migrar_legado(apps, schema_editor):
    TurmaGrupo = apps.get_model("listaEspera", "TurmaGrupo")
    Turma = apps.get_model("listaEspera", "Turma")
    Grupo = apps.get_model("listaEspera", "Grupo")
    MembroTurmaGrupo = apps.get_model("listaEspera", "MembroTurmaGrupo")
    MembroTurma = apps.get_model("listaEspera", "MembroTurma")
    MembroGrupo = apps.get_model("listaEspera", "MembroGrupo")
    ProjetoTurmaGrupo = apps.get_model("listaEspera", "ProjetoTurmaGrupo")
    Vinculo = apps.get_model("listaEspera", "VinculoProjetoInstitucional")

    agora = timezone.now()
    turmas_por_legado = {}
    grupos_por_legado = {}

    antigos = list(TurmaGrupo.objects.select_related("programa").order_by("criado_em", "id"))
    for antigo in antigos:
        if antigo.tipo != "turma":
            continue
        turma = Turma.objects.create(
            programa_id=antigo.programa_id,
            nome=nome_disponivel(Turma.objects.filter(programa_id=antigo.programa_id), antigo.nome),
            descricao=antigo.descricao,
            professor_responsavel_id=antigo.professor_responsavel_id,
            status=antigo.status,
            criado_por_id=antigo.criado_por_id,
            legado_id=antigo.id,
            criado_em=antigo.criado_em or agora,
            atualizado_em=antigo.atualizado_em or agora,
        )
        turmas_por_legado[antigo.id] = turma

    for antigo in antigos:
        if antigo.tipo != "grupo":
            continue
        turma = Turma.objects.filter(programa_id=antigo.programa_id).order_by("criado_em", "id").first()
        if turma is None:
            turma = Turma.objects.create(
                programa_id=antigo.programa_id,
                nome=nome_disponivel(Turma.objects.filter(programa_id=antigo.programa_id), "Turma legada"),
                descricao="Criada automaticamente para preservar um grupo legado sem turma de origem.",
                professor_responsavel_id=antigo.professor_responsavel_id,
                status=antigo.status,
                criado_por_id=antigo.criado_por_id,
                legado_id=antigo.id,
                criado_em=antigo.criado_em or agora,
                atualizado_em=antigo.atualizado_em or agora,
            )
        grupo = Grupo.objects.create(
            turma_id=turma.id,
            nome=nome_disponivel(Grupo.objects.filter(turma_id=turma.id), antigo.nome),
            descricao=antigo.descricao,
            status=antigo.status,
            criado_por_id=antigo.criado_por_id,
            legado_id=antigo.id,
            criado_em=antigo.criado_em or agora,
            atualizado_em=antigo.atualizado_em or agora,
        )
        grupos_por_legado[antigo.id] = grupo

    for membro in MembroTurmaGrupo.objects.all().iterator():
        antigo = TurmaGrupo.objects.get(pk=membro.turma_grupo_id)
        if antigo.tipo == "turma" and antigo.id in turmas_por_legado:
            MembroTurma.objects.get_or_create(
                turma_id=turmas_por_legado[antigo.id].id,
                usuario_id=membro.usuario_id,
                defaults={"status": membro.status, "entrou_em": membro.entrou_em or agora},
            )
        elif antigo.id in grupos_por_legado:
            MembroGrupo.objects.get_or_create(
                grupo_id=grupos_por_legado[antigo.id].id,
                usuario_id=membro.usuario_id,
                defaults={
                    "representante": membro.papel == "professor",
                    "status": membro.status,
                    "entrou_em": membro.entrou_em or agora,
                },
            )

    for vinculo_antigo in ProjetoTurmaGrupo.objects.all().iterator():
        antigo = TurmaGrupo.objects.get(pk=vinculo_antigo.turma_grupo_id)
        if antigo.tipo == "turma":
            turma = turmas_por_legado.get(antigo.id)
            grupo_id = None
        else:
            grupo = grupos_por_legado.get(antigo.id)
            turma = Turma.objects.filter(grupos__id=grupo.id).first() if grupo else None
            grupo_id = grupo.id if grupo else None
        if turma is None:
            continue
        Vinculo.objects.get_or_create(
            projeto_id=vinculo_antigo.projeto_id,
            defaults={
                "turma_id": turma.id,
                "grupo_id": grupo_id,
                "vinculado_por_id": vinculo_antigo.vinculado_por_id,
                "legado_id": vinculo_antigo.id,
                "vinculado_em": vinculo_antigo.vinculado_em or agora,
            },
        )


def reverter_legado(apps, schema_editor):
    Vinculo = apps.get_model("listaEspera", "VinculoProjetoInstitucional")
    MembroGrupo = apps.get_model("listaEspera", "MembroGrupo")
    MembroTurma = apps.get_model("listaEspera", "MembroTurma")
    Grupo = apps.get_model("listaEspera", "Grupo")
    Turma = apps.get_model("listaEspera", "Turma")

    Vinculo.objects.filter(legado_id__isnull=False).delete()
    MembroGrupo.objects.filter(grupo__legado_id__isnull=False).delete()
    MembroTurma.objects.filter(turma__legado_id__isnull=False).delete()
    Grupo.objects.filter(legado_id__isnull=False).delete()
    Turma.objects.filter(legado_id__isnull=False).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("listaEspera", "0018_vinculoprojetoinstitucional_legado_id"),
    ]

    operations = [migrations.RunPython(migrar_legado, reverter_legado)]
