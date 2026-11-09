from django.shortcuts import redirect, render
from django.db.models import Count
from django.utils import timezone
from plataforma.experience import _decorar_projetos
from core.rankings import ranked_projects

from plataforma.models import EventoCalendario, ProgramaInstitucional, Project


def index(request):
    """Homepage institucional e porta de entrada do produto."""
    organizacao = getattr(request, "organizacao", None)
    afiliacao = getattr(request, "membro_organizacao", None)
    if organizacao is not None and afiliacao is not None:
        projetos = organizacao.projetos.filter(
            visibility=Project.VISIBILITY_PUBLIC,
        ).select_related("owner", "vinculo_institucional__turma__programa").annotate(
            relevance=Count("votes", distinct=True),
            total_estrelas=Count("votes", distinct=True),
            total_membros=Count("memberships", distinct=True),
        )
        autonomos = projetos.filter(vinculo_institucional__isnull=True).order_by("-updated_at", "-pk")
        vinculados = projetos.filter(
            vinculo_institucional__turma__programa__status=ProgramaInstitucional.STATUS_PUBLICADO,
            vinculo_institucional__turma__programa__organizacao=organizacao,
        ).order_by("-updated_at", "-pk")
        ranking = ranked_projects(projetos.filter(votes__isnull=False).distinct(), tenant_id=organizacao.pk)[:5]
        agenda = EventoCalendario.objects.filter(
            organizacao=organizacao, aluno=request.user, data__gte=timezone.localdate(),
        ).exclude(tipo=EventoCalendario.TIPO_TRABALHO, status=EventoCalendario.STATUS_ENTREGUE).order_by(
            "data", "horario", "pk",
        ).only("titulo", "data", "horario", "tipo")[:2]
        return render(request, "institutional/home.html", {
            "organizacao": organizacao,
            "afiliacao": afiliacao,
            "nav_ativo": "inicio",
            "projetos_autonomos": _decorar_projetos(list(autonomos[:4])),
            "projetos_vinculados": _decorar_projetos(list(vinculados[:4])),
            "total_autonomos": autonomos.count(),
            "total_vinculados": vinculados.count(),
            "ranking_projetos": _decorar_projetos(list(ranking)),
            "agenda_proximos": list(agenda),
            "agenda_hoje": timezone.localdate(),
        })
    latest_projects = Project.objects.filter(
        visibility=Project.VISIBILITY_PUBLIC,
        organizacao__isnull=True,
    ).select_related("owner")[:3]
    return render(request, "core/index.html", {"latest_projects": latest_projects})
