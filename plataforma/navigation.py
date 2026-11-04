"""URLs entre ambientes: origem configurada ou domínio institucional cadastrado."""

from django.conf import settings
from django.urls import reverse


def global_home_url(request):
    host = request.get_host().split(":", 1)[0].lower()
    if host.endswith(".app.github.dev"):
        return f"{request.scheme}://{request.get_host()}/"
    public_url = getattr(settings, "PUBLIC_APP_URL", "").strip().rstrip("/")
    if public_url and "localhost" not in public_url:
        return f"{public_url}/"
    return f"{request.scheme}://{settings.PALACIO_BASE_DOMAIN}/"


def project_notification_url(request, project):
    path = reverse("plataforma:project_detail", kwargs={"pk": project.pk})
    if project.organizacao_id is None:
        return global_home_url(request).rstrip("/") + path
    # Não usa Host recebido do cliente: só um domínio ativo do tenant do objeto.
    domain = project.organizacao.dominios.filter(status_verificacao="ativo").order_by(
        "-principal", "hostname"
    ).first()
    if domain is None:
        raise ValueError("Projeto institucional sem domínio ativo para notificação.")
    return f"{request.scheme}://{domain.hostname}{path}"
