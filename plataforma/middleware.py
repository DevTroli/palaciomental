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
        self.dev_cookie_name = "pm_dev_tenant"
        self.dev_query_param = getattr(settings, "DEV_TENANT_QUERY_PARAM", "tenant")

    def __call__(self, request):
        hostname = self._hostname(request)
        dev_organizacao = self._resolve_development_tenant(request)
        organizacao = dev_organizacao or self._resolve_organization(hostname)
        is_dev_tenant = dev_organizacao is not None

        if organizacao is None:
            if self._is_tenant_host(hostname):
                return HttpResponseNotFound("Ambiente institucional não encontrado.")
            return self.get_response(request)

        request.organizacao = organizacao
        request.tenant = organizacao

        if self._is_public_auth_path(request.path):
            return self._finish(request, self.get_response(request), is_dev_tenant)

        if not request.user.is_authenticated:
            return self._finish(request, redirect_to_login(request.get_full_path(), settings.LOGIN_URL), is_dev_tenant)

        affiliation = MembroOrganizacao.objects.filter(
            organizacao=organizacao,
            usuario=request.user,
            status=MembroOrganizacao.STATUS_ATIVA,
        ).first()
        if affiliation is None:
            return self._finish(request, HttpResponseForbidden("Sua conta não possui afiliação ativa neste ambiente institucional."), is_dev_tenant)

        request.membro_organizacao = affiliation
        return self._finish(request, self.get_response(request), is_dev_tenant)

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

    def _resolve_development_tenant(self, request):
        """Permite testar um tenant no Codespaces sem simular DNS de produção."""
        if not settings.DEBUG:
            return None
        slug = (request.GET.get(self.dev_query_param) or request.COOKIES.get(self.dev_cookie_name) or "").strip().lower()
        if not slug:
            return None
        return Organizacao.objects.filter(slug=slug, status=Organizacao.STATUS_ATIVA).first()

    def _finish(self, request, response, is_dev_tenant):
        if is_dev_tenant and settings.DEBUG:
            slug = request.GET.get(self.dev_query_param) or request.COOKIES.get(self.dev_cookie_name)
            response.set_cookie(self.dev_cookie_name, slug, max_age=86400, httponly=True, samesite="Lax")
        return response

    def _is_tenant_host(self, hostname):
        return hostname.endswith(f".{self.base_domain}") and hostname != self.base_domain

    def _is_reserved_host(self, hostname):
        return hostname in self.reserved_hosts or hostname.split(".", 1)[0] in self.reserved_hosts

    @staticmethod
    def _is_public_auth_path(path):
        return path.startswith(("/entrar/", "/cadastrar/", "/sair/", "/static/", "/favicon", "/convites/grupos/", "/convites/organizacao/"))
