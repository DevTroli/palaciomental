from .branding import organization_branding
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
    return {
        "global_home_url": global_home_url(request),
        "personal_workspace_url": (
            global_home_url(request).rstrip("/")
            + reverse("plataforma:profile", args=[request.user.username])
            if request.user.is_authenticated else global_home_url(request)
        ),
        **organization_branding(organizacao),
    }


def institutional_experience(request):
    if not getattr(request, "membro_organizacao", None):
        return {"layout_template": "base.html"}
    from .experience import _contexto_base
    return {"layout_template": "institutional/experience/base.html", **_contexto_base(request)}
