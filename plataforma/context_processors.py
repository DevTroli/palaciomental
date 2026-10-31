from .validators import CORES_SEMANTICAS


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
