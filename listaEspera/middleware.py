from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, HttpResponseNotFound

from .models import MembroOrganizacao, Organizacao, DominioOrganizacao


class TenantResolutionMiddleware:
    """Resolve o tenant pelo host sem permitir fallback silencioso entre organizações."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.base_domain = settings.PALACIO_BASE_DOMAIN.lower().strip(".")
        self.reserved_hosts = set(getattr(settings, "TENANT_RESERVED_HOSTS", ()))

    def __call__(self, request):
        hostname = self._hostname(request)
        organizacao = self._resolve_organization(hostname)

        if organizacao is None:
            if self._is_tenant_host(hostname):
                return HttpResponseNotFound("Ambiente institucional não encontrado.")
            return self.get_response(request)

        request.organizacao = organizacao
        request.tenant = organizacao

        if self._is_public_auth_path(request.path):
            return self.get_response(request)

        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)

        affiliation = MembroOrganizacao.objects.filter(
            organizacao=organizacao,
            usuario=request.user,
            status=MembroOrganizacao.STATUS_ATIVA,
        ).first()
        if affiliation is None:
            return HttpResponseForbidden("Sua conta não possui afiliação ativa neste ambiente institucional.")

        request.membro_organizacao = affiliation
        return self.get_response(request)

    def _hostname(self, request):
        return request.get_host().split(":", 1)[0].lower().rstrip(".")

    def _resolve_organization(self, hostname):
        if self._is_reserved_host(hostname) or hostname == self.base_domain:
            return None
        return (
            Organizacao.objects.filter(
                status=Organizacao.STATUS_ATIVA,
                dominios__hostname=hostname,
                dominios__status_verificacao="ativo",
            )
            .distinct()
            .first()
        )

    def _is_tenant_host(self, hostname):
        return hostname.endswith(f".{self.base_domain}") and hostname != self.base_domain

    def _is_reserved_host(self, hostname):
        return hostname in self.reserved_hosts or hostname.split(".", 1)[0] in self.reserved_hosts

    @staticmethod
    def _is_public_auth_path(path):
        return path.startswith(("/entrar/", "/cadastrar/", "/sair/", "/static/", "/favicon"))
