from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase, override_settings

from plataforma.admin import OrganizacaoAdmin
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


    def test_active_primary_domain_generates_local_url(self):
        url, message = self.modeladmin._tenant_access(self.request, self.organization())
        self.assertEqual(url, "http://camp.localhost:8000/")
        self.assertIn("afiliação", message)


    def test_permission_required(self):
        self.permission.return_value = False
        url, _ = self.modeladmin._tenant_access(self.request, self.organization())
        self.assertIsNone(url)


    @override_settings(DEBUG=False)
    def test_production_domain_uses_https_without_local_port(self):
        obj = self.organization([self.domain("camp.example.com")])
        self.assertEqual(self.modeladmin._tenant_access(self.request, obj)[0], "https://camp.example.com/")
