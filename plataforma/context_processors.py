from urllib.parse import urlsplit, urlunsplit
from django.conf import settings
from django.urls import reverse

from .branding import organization_branding
from .navigation import global_home_url


def _status_page_url(organizacao):
    try:
        endpoint = urlsplit(getattr(settings, "STATUS_API_URL", ""))
        has_userinfo = endpoint.username is not None or endpoint.password is not None
    except ValueError:
        return ""
    compose_http = endpoint.netloc == "status-api:8080"
    local_http = (
        settings.DEBUG and settings.GUARDIAO_LOCAL_HTTP and endpoint.scheme == "http"
        and (compose_http or endpoint.hostname in {"localhost", "127.0.0.1", "::1"})
    )
    if (not (endpoint.scheme == "https" or local_http) or not endpoint.netloc or has_userinfo
            or endpoint.query or endpoint.fragment or not endpoint.path.endswith("/v1/status")):
        return ""
    path = endpoint.path.removesuffix("/v1/status").rstrip("/")
    # O Compose publica a porta do serviço no loopback do navegador.
    host = "127.0.0.1:8080" if local_http and compose_http else endpoint.netloc
    base = urlunsplit((endpoint.scheme, host, path, "", "")).rstrip("/")
    if organizacao is None:
        return f"{base}/status"
    return f"{base}/status/org/{organizacao.slug}"


def inbox_unread_count(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"inbox_unread_count": 0}
    return {"inbox_unread_count": request.user.notifications.filter(read_at__isnull=True).count()}


def tenant_branding(request):
    """Disponibiliza branding controlado para qualquer tela contextual do tenant."""
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None:
        return {"global_status_url": _status_page_url(None)}
    return {
        "global_home_url": global_home_url(request),
        "tenant_status_url": _status_page_url(organizacao),
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
