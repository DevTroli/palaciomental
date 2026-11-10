"""Fotografia agregada do tenant; nunca inclui conteúdo de projetos privados."""

from django.db.models import Count

from .models import MembroOrganizacao, Project


def management_distributions(organization):
    project_counts = dict(
        organization.projetos.order_by().values_list("status").annotate(total=Count("pk"))
    )
    member_counts = dict(
        organization.afiliacoes.filter(status=MembroOrganizacao.STATUS_ATIVA)
        .order_by().values_list("papel").annotate(total=Count("pk"))
    )
    return {
        "projects": {
            "label": "Projetos por situação",
            "labels": [label for _, label in Project.STATUS_CHOICES],
            "values": [project_counts.get(status, 0) for status, _ in Project.STATUS_CHOICES],
        },
        "members": {
            "label": "Afiliações ativas por papel",
            "labels": [label for _, label in MembroOrganizacao.PAPEL_CHOICES],
            "values": [member_counts.get(role, 0) for role, _ in MembroOrganizacao.PAPEL_CHOICES],
        },
    }
