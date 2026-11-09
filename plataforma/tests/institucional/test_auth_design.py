import hashlib
from datetime import timedelta
from tempfile import TemporaryDirectory

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from plataforma.models import ConviteOrganizacao, IdentidadeOrganizacao, MembroOrganizacao
from .base import PortalInstitucionalBase

HOST = "camppg.palaciomental.com.br"


class TenantAuthDesignTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.identity = IdentidadeOrganizacao.objects.create(organizacao=self.organization,
            nome_exibicao="Instituto Horizonte", logo=self.logo_file(),
            tema={"primary": "#213E55", "accent": "#C9E496", "surface": "#FAFAF6"})
        self.token = "design-invitation-local"
        self.invitation = ConviteOrganizacao.objects.create(organizacao=self.organization,
            email="convidado@example.com", papel="membro", convidado_por=self.user,
            hash_token=hashlib.sha256(self.token.encode()).hexdigest(),
            expira_em=timezone.now() + timedelta(days=7))
        self.path = reverse("plataforma:institutional_organization_invite_accept", args=[self.token])

    def test_login_and_invitation_use_tenant_identity_without_sidebar(self):
        for path in ("/entrar/", self.path):
            response = self.client.get(path, HTTP_HOST=HOST)
            self.assertContains(response, "Instituto Horizonte")
            self.assertContains(response, self.identity.logo.url)
            self.assertContains(response, "#213E55")
            self.assertContains(response, "tenant-auth.css")
            self.assertNotContains(response, 'class="camp-sidebar"')
        self.assertContains(response, 'aria-current="step"')

    def test_registration_stays_closed_and_invitation_keeps_its_login_return(self):
        response = self.client.get("/cadastrar/", HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Cadastro fechado", status_code=403)
        self.assertContains(response, "Instituto Horizonte", status_code=403)
        response = self.client.get(self.path, HTTP_HOST=HOST)
        self.assertNotContains(response, 'name="email"')
        self.assertContains(response, "convidado@example.com")
        self.assertEqual(response.context["login_url"], reverse("plataforma:login") + "?next=" + self.path.replace("/", "%2F"))

    def test_invalid_login_and_password_confirmation_keep_accessible_error_descriptions(self):
        response = self.client.post("/entrar/", {"username": "desconhecido", "password": "invalida"}, HTTP_HOST=HOST)
        self.assertContains(response, 'id="auth-errors"')
        self.assertContains(response, 'data-auth-error-summary')
        response = self.client.post(self.path, {"action": "register", "username": "novo",
            "password1": "Uma-senha-forte-123", "password2": "outra-senha"}, HTTP_HOST=HOST)
        self.assertContains(response, 'id="id_password2_error"')
        self.assertContains(response, 'id="id_password1_helptext"')
        self.assertContains(response, 'name="action" value="register"')
        self.assertFalse(MembroOrganizacao.objects.filter(usuario__username="novo").exists())
