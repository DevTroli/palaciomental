from typing import cast
from django.core.handlers.wsgi import WSGIRequest
from django.contrib.auth.models import AnonymousUser

from datetime import timedelta
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import timezone

from plataforma.branding import invitation_branding


class BrandingRequest(WSGIRequest):
    organizacao: SimpleNamespace


@override_settings(
    ALLOWED_HOSTS=["campus.palaciomental.com.br"],
    PUBLIC_APP_URL="https://palaciomental.com.br",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class BrandingEmailTests(SimpleTestCase):
    def setUp(self):
        self.request = cast(BrandingRequest, RequestFactory().get("/", secure=True, HTTP_HOST="campus.palaciomental.com.br"))
        self.request.user = AnonymousUser()
        self.identity = SimpleNamespace(
            nome_exibicao="Campus & Projetos", cor_primaria="azul-sobrio",
            cor_destaque="verde-institucional", cor_fundo="bege-claro",
            logo=SimpleNamespace(url="https://media.palaciomental.com.br/media/tenants/campus/logo.png"),
        )
        self.organization = SimpleNamespace(nome="Campus", slug="campus", identidade=self.identity)
        self.request.organizacao = self.organization
        self.invitation = SimpleNamespace(
            pk="test-invitation", organizacao=self.organization,
            email="recipient@example.com", expira_em=timezone.now() + timedelta(days=7),
            get_papel_display=lambda: "Gestor",
            convidado_por=SimpleNamespace(get_full_name=lambda: "", username="coordenador"),
        )

    def context(self):
        return {
            **invitation_branding(self.request, self.organization),
            "convite": self.invitation, "convidado_por": self.invitation.convidado_por,
            "invite_url": "https://campus.palaciomental.com.br/convites/token/",
            "grupo": SimpleNamespace(nome="Grupo de projetos"),
            "programa": SimpleNamespace(nome="Programa piloto"),
        }


    def test_local_media_url_is_absolute_for_email(self):
        self.identity.logo.url = "/media/tenants/campus/logo.png"
        context = invitation_branding(self.request, self.organization)
        self.assertEqual(context["tenant_logo_url"], "https://campus.palaciomental.com.br/media/tenants/campus/logo.png")


    def test_both_email_templates_have_branding_and_action(self):
        for template in ("organization_invitation", "institutional_invitation"):
            with self.subTest(template=template):
                html = render_to_string(f"emails/{template}.html", self.context())
                self.assertIn(self.identity.logo.url, html)
                self.assertIn("background:#315A76", html)
                self.assertIn("background:#5C9F63;color:#000000", html)
                self.assertIn("Campus &amp; Projetos", html)
                self.assertIn("Palácio Mental", html)
                self.assertIn("contexto, a autoria", html)
                self.assertIn('class="pm-footer-logo"', html)
                self.assertIn('class="pm-footer-copy"', html)
                self.assertIn('valign="middle"', html)
                self.assertIn("Ambiente institucional no Palácio Mental", html)
                self.assertIn("recipient@example.com", html)
                self.assertIn("https://campus.palaciomental.com.br/convites/token/", html)
                self.assertNotIn("src=\"\"", html)
