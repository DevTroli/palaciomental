"""Regras de apresentação da agenda, além do isolamento de linhas por tenant."""
from .models import Project


def visible_events(events, request):
    """Um vínculo antigo não torna público um projeto que mudou de visibilidade."""
    result = list(events)
    for event in result:
        project = event.projeto
        visible = project is not None and project.organizacao_id == request.organizacao.pk and (
            project.owner_id == request.user.pk or project.visibility == Project.VISIBILITY_PUBLIC
        )
        event.projeto_visivel = project if visible else None
    return result
