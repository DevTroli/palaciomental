from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase, override_settings

from plataforma.admin import OrganizacaoAdmin
from plataforma.admin_tenant_access import TenantAccessAdminMixin
from plataforma.models import Organizacao


@override_settings(DEBUG=True, ALLOWED_HOSTS=[".localhost"])
class TenantAccessAdminTests(SimpleTestCase):
    def setUp(self):
        self.modeladmin = OrganizacaoAdmin(Organizacao, admin.site)
        self.factory = RequestFactory()
        self.request = self.factory.get("/admin/", HTTP_HOST="localhost:8000")
        permission = patch.object(self.modeladmin, "has_view_or_change_permission", return_value=True)
        self.permission = permission.start()
        self.addCleanup(permission.stop)

    def domain(self, hostname="camp.localhost", principal=True, status="ativo"):
        return SimpleNamespace(hostname=hostname, principal=principal, status_verificacao=status)

    def organization(self, domains=None, status=None):
        domains = [self.domain()] if domains is None else domains
        return SimpleNamespace(pk=1, STATUS_ATIVA=Organizacao.STATUS_ATIVA, status=status or Organizacao.STATUS_ATIVA, dominios=SimpleNamespace(all=lambda: domains))

    def test_registered_admin_uses_mixin(self):
        self.assertIsInstance(admin.site._registry[Organizacao], TenantAccessAdminMixin)

    def test_active_primary_domain_generates_local_url(self):
        url, message = self.modeladmin._tenant_access(self.request, self.organization())
        self.assertEqual(url, "http://camp.localhost:8000/")
        self.assertIn("afiliação", message)

    def test_inactive_or_unsaved_organization_has_no_link(self):
        self.assertIsNone(self.modeladmin._tenant_access(self.request, self.organization(status="suspensa"))[0])
        self.assertIsNone(self.modeladmin._tenant_access(self.request, None)[0])
        obj = self.organization()
        obj.pk = None
        self.assertIsNone(self.modeladmin._tenant_access(self.request, obj)[0])

    def test_requires_one_active_primary_domain(self):
        cases = [[], [self.domain(principal=False)], [self.domain(status="pendente")], [self.domain(), self.domain("other.localhost")]]
        for domains in cases:
            with self.subTest(domains=domains):
                self.assertIsNone(self.modeladmin._tenant_access(self.request, self.organization(domains))[0])

    def test_invalid_hostname_has_no_link(self):
        obj = self.organization([self.domain("camp.localhost:8000")])
        self.assertIsNone(self.modeladmin._tenant_access(self.request, obj)[0])

    def test_permission_required(self):
        self.permission.return_value = False
        url, _ = self.modeladmin._tenant_access(self.request, self.organization())
        self.assertIsNone(url)

    def test_list_button_is_safe_and_keeps_existing_columns(self):
        columns = self.modeladmin.get_list_display(self.request)
        self.assertEqual(columns[:-1], self.modeladmin.list_display)
        html = columns[-1](self.organization())
        self.assertIn('href="http://camp.localhost:8000/"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn("Abrir ambiente", html)
        self.assertNotIn("<a", columns[-1](self.organization([])))

    def test_list_callbacks_do_not_share_request_state(self):
        first = self.modeladmin.get_list_display(self.request)[-1]
        other = self.factory.get("/admin/", HTTP_HOST="localhost:9000")
        second = self.modeladmin.get_list_display(other)[-1]
        self.assertIn(":8000/", first(self.organization()))
        self.assertIn(":9000/", second(self.organization()))
        self.assertIn(":8000/", first(self.organization()))

    def test_change_form_context_and_template(self):
        context = {"original_context": True}
        with patch.object(admin.ModelAdmin, "render_change_form", side_effect=lambda request, context, **kwargs: context):
            result = self.modeladmin.render_change_form(self.request, context, change=True, obj=self.organization())
        self.assertEqual(result["tenant_access_url"], "http://camp.localhost:8000/")
        self.assertNotIn("tenant_access_url", context)
        template = self.modeladmin.change_form_template
        assert isinstance(template, str)
        self.assertIsNotNone(get_template(template))

    @override_settings(DEBUG=False)
    def test_local_domain_is_not_linked_in_production(self):
        self.assertIsNone(self.modeladmin._tenant_access(self.request, self.organization())[0])

    @override_settings(DEBUG=False)
    def test_production_domain_uses_https_without_local_port(self):
        obj = self.organization([self.domain("camp.example.com")])
        self.assertEqual(self.modeladmin._tenant_access(self.request, obj)[0], "https://camp.example.com/")
