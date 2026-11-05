from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html

from .admin_tenant_links import build_tenant_url


class TenantAccessAdminMixin:
    change_form_template = "admin/tenant_change_form.html"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("dominios")

    def _tenant_access(self, request, obj):
        if obj is None or not obj.pk:
            return None, "Salve a organização e configure um domínio principal ativo."
        if not self.has_view_or_change_permission(request, obj):
            return None, "Acesso indisponível."
        if obj.status != obj.STATUS_ATIVA:
            return None, "A organização precisa estar ativa."
        domains = [domain for domain in obj.dominios.all() if domain.principal and domain.status_verificacao == "ativo"]
        if len(domains) != 1:
            return None, "Configure exatamente um domínio principal com verificação ativa."
        url = build_tenant_url(domains[0].hostname, debug=settings.DEBUG, request_host=request.get_host(), request_scheme=request.scheme)
        if not url:
            return None, "Confira o hostname sem protocolo/porta e a configuração do ambiente local."
        return url, "O acesso continua sujeito a login e afiliação ativa."

    def get_list_display(self, request):
        @admin.display(description="Ambiente")
        def abrir_ambiente(obj):
            url, message = self._tenant_access(request, obj)
            if not url:
                return message
            return format_html('<a class="button" href="{}" target="_blank" rel="noopener noreferrer" title="{}">Abrir ambiente</a>', url, message)

        return (*super().get_list_display(request), abrir_ambiente)

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        url, message = self._tenant_access(request, obj)
        context = {**context, "tenant_access_url": url, "tenant_access_message": message}
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)
