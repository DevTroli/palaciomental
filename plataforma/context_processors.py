from .validators import CORES_SEMANTICAS
from .navigation import global_home_url
from django.urls import reverse


def inbox_unread_count(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"inbox_unread_count": 0}
    return {"inbox_unread_count": request.user.notifications.filter(read_at__isnull=True).count()}


def tenant_branding(request):
    """Disponibiliza branding controlado para qualquer tela contextual do tenant."""
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None:
        return {}
    identidade = getattr(organizacao, "identidade", None)
    return {
        "global_home_url": global_home_url(request),
        "personal_workspace_url": (
            global_home_url(request).rstrip("/")
            + reverse("plataforma:profile", args=[request.user.username])
            if request.user.is_authenticated else global_home_url(request)
        ),
        "tenant_display_name": getattr(identidade, "nome_exibicao", "") or organizacao.nome,
        "tenant_identidade": identidade,
        "tenant_logo_url": identidade.logo.url if identidade and identidade.logo else "",
        "tenant_primary_color": CORES_SEMANTICAS.get(
            getattr(identidade, "cor_primaria", ""), CORES_SEMANTICAS["roxo-institucional"]
        ),
        "tenant_accent_color": CORES_SEMANTICAS.get(
            getattr(identidade, "cor_destaque", ""), CORES_SEMANTICAS["verde-institucional"]
        ),
        "tenant_background_color": CORES_SEMANTICAS.get(
            getattr(identidade, "cor_fundo", ""), CORES_SEMANTICAS["bege-claro"]
        ),
    }
