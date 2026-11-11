from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from plataforma.models import MembroOrganizacao
from .base import PortalInstitucionalBase


@override_settings(REDIS_URL="")
class AccessiYesLayoutsTests(PortalInstitucionalBase):
    def assert_widget_once(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cdn-cookieyes.com/widgets/accessibility.js?id=", count=1)
        self.assertContains(response, "window._cyA11yConfig", count=1)
        html = response.content.decode()
        self.assertLess(html.index("window._cyA11yConfig"), html.index("cdn-cookieyes.com/widgets/accessibility.js"))

    @patch("plataforma.views._fetch_status_api", return_value=None)
    def test_global_and_tenant_layouts_include_widget(self, _status):
        for path in ("/", "/entrar/", "/cadastrar/", "/status/"):
            with self.subTest(path=path):
                self.assert_widget_once(self.client.get(path, HTTP_HOST="palaciomental.com.br"))
        self.assert_widget_once(self.client.get("/entrar/", HTTP_HOST="camppg.palaciomental.com.br"))
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user)
        self.client.force_login(self.user)
        for path in ("/", "/programas/", "/calendario/", "/perfil/"):
            with self.subTest(path=path):
                self.assert_widget_once(self.client.get(path, HTTP_HOST="camppg.palaciomental.com.br"))

    def test_admin_pages_include_widget_once(self):
        self.assert_widget_once(self.client.get(reverse("admin:login"), HTTP_HOST="palaciomental.com.br"))
        self.pm_staff.is_superuser = True
        self.pm_staff.save(update_fields=["is_superuser"])
        self.client.force_login(self.pm_staff)
        for path in (reverse("admin:index"), reverse("admin:auth_user_changelist")):
            with self.subTest(path=path):
                self.assert_widget_once(self.client.get(path, HTTP_HOST="palaciomental.com.br"))
