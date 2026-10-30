from django.shortcuts import redirect, render
from django.db.models import Count, Q

from plataforma.models import Grupo, MembroGrupo, MembroOrganizacao, MembroTurma, ProgramaInstitucional, Project, Turma
from plataforma.validators import CORES_SEMANTICAS


def index(request):
    """Homepage institucional e porta de entrada do produto."""
    organizacao = getattr(request, "organizacao", None)
    afiliacao = getattr(request, "membro_organizacao", None)
    if organizacao is not None and afiliacao is not None:
        identidade = getattr(organizacao, "identidade", None)
        primary_color = CORES_SEMANTICAS.get(getattr(identidade, "cor_primaria", ""), CORES_SEMANTICAS["roxo-institucional"])
        accent_color = CORES_SEMANTICAS.get(getattr(identidade, "cor_destaque", ""), CORES_SEMANTICAS["verde-institucional"])
        background_color = CORES_SEMANTICAS.get(getattr(identidade, "cor_fundo", ""), CORES_SEMANTICAS["bege-claro"])
        programas = organizacao.programas.filter(
            status=ProgramaInstitucional.STATUS_PUBLICADO,
        ).prefetch_related("turmas__grupos")[:6]
        grupos_base = Grupo.objects.filter(
            turma__programa__organizacao=organizacao,
            turma__programa__status=ProgramaInstitucional.STATUS_PUBLICADO,
            status=Grupo.STATUS_ATIVO,
        ).select_related("turma__programa", "turma__professor_responsavel").annotate(membros_count=Count("membros", distinct=True))
        projetos = organizacao.projetos.filter(
            visibility=Project.VISIBILITY_PUBLIC,
        ).select_related("owner").annotate(relevance=Count("votes", distinct=True)).order_by("-relevance", "-updated_at")[:6]
        grupos = grupos_base[:8]
        turmas = Turma.objects.filter(
            programa__organizacao=organizacao,
            programa__status=ProgramaInstitucional.STATUS_PUBLICADO,
            status=Turma.STATUS_ATIVO,
        ).select_related("programa", "professor_responsavel").annotate(membros_count=Count("membros", distinct=True))
        if afiliacao.papel not in {MembroOrganizacao.PAPEL_PROPRIETARIO, MembroOrganizacao.PAPEL_GESTOR}:
            turmas = turmas.filter(
                Q(professor_responsavel=request.user)
                | Q(membros__usuario=request.user, membros__status=MembroTurma.STATUS_ATIVO),
                programa__organizacao=organizacao,
                programa__status=ProgramaInstitucional.STATUS_PUBLICADO,
                status=Turma.STATUS_ATIVO,
            ).distinct()[:8]
            grupos = grupos_base.filter(
                Q(turma__professor_responsavel=request.user)
                | Q(membros__usuario=request.user, membros__status=MembroGrupo.STATUS_ATIVO),
            ).distinct()[:8]
        else:
            turmas = turmas[:8]
        return render(
            request,
            "institutional/home.html",
            {
                "organizacao": organizacao,
                "afiliacao": afiliacao,
                "identidade": identidade,
                "programas": programas,
                "turmas": turmas,
                "grupos_abertos": grupos,
                "projetos": projetos,
                "ranking_provisorio": True,
                "tenant_primary_color": primary_color,
                "tenant_accent_color": accent_color,
                "tenant_background_color": background_color,
            },
        )
    latest_projects = Project.objects.filter(
        visibility=Project.VISIBILITY_PUBLIC,
        organizacao__isnull=True,
    ).select_related("owner")[:3]
    return render(request, "core/index.html", {"latest_projects": latest_projects})
