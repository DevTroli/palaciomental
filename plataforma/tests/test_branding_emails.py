from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import timezone

from plataforma.branding import contrasting_text, invitation_branding, organization_branding
from plataforma.context_processors import tenant_branding
from plataforma.views import _send_group_invitation_email, _send_organization_invitation_email


@override_settings(
    ALLOWED_HOSTS=["campus.palaciomental.com.br"],
    PUBLIC_APP_URL="https://palaciomental.com.br",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class BrandingEmailTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/", secure=True, HTTP_HOST="campus.palaciomental.com.br")
        self.request.user = SimpleNamespace(is_authenticated=False)
        self.identity = SimpleNamespace(
            nome_exibicao="Campus & Projetos", cor_primaria="azul-sobrio",
            cor_destaque="verde-institucional", cor_fundo="bege-claro",
            logo=SimpleNamespace(url="https://media.palaciomental.com.br/media/tenants/campus/logo.png"),
        )
        self.organization = SimpleNamespace(nome="Campus", identidade=self.identity)
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

    def test_storage_cdn_url_is_preserved(self):
        context = invitation_branding(self.request, self.organization)
        self.assertEqual(context["tenant_logo_url"], self.identity.logo.url)
        self.assertTrue(context["pm_logo_url"].startswith("https://"))
        self.assertIn("/static/img/mind_palace_logo.png", context["pm_logo_url"])

    def test_local_media_url_is_absolute_for_email(self):
        self.identity.logo.url = "/media/tenants/campus/logo.png"
        context = invitation_branding(self.request, self.organization)
        self.assertEqual(context["tenant_logo_url"], "https://campus.palaciomental.com.br/media/tenants/campus/logo.png")

    def test_no_logo_and_no_identity_have_safe_defaults(self):
        self.identity.logo = None
        self.assertEqual(organization_branding(self.organization)["tenant_logo_url"], "")
        self.organization.identidade = None
        context = organization_branding(self.organization)
        self.assertEqual(context["tenant_display_name"], "Campus")
        self.assertEqual(context["tenant_primary_color"], "#6E4AA3")

    def test_invalid_semantic_color_never_becomes_css(self):
        self.identity.cor_primaria = "red; background:url(https://untrusted.invalid)"
        self.assertEqual(organization_branding(self.organization)["tenant_primary_color"], "#6E4AA3")

    def test_text_contrast_for_both_palette_extremes(self):
        self.assertEqual(contrasting_text("#ffffff"), "#000000")
        self.assertEqual(contrasting_text("#000000"), "#ffffff")
        self.assertEqual(contrasting_text("#5c9f63"), "#000000")

    def test_web_context_uses_storage_url_and_shared_palette(self):
        context = tenant_branding(self.request)
        self.assertEqual(context["tenant_logo_url"], self.identity.logo.url)
        self.assertEqual(context["tenant_primary_color"], "#315A76")

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
                self.assertIn("recipient@example.com", html)
                self.assertIn("https://campus.palaciomental.com.br/convites/token/", html)
                self.assertNotIn("src=\"\"", html)

    def test_email_without_logo_keeps_name_and_pm_mark(self):
        self.identity.logo = None
        html = render_to_string("emails/organization_invitation.html", self.context())
        self.assertNotIn('alt="Logo de ', html)
        self.assertIn('alt="Palácio Mental"', html)
        self.assertIn("Campus &amp; Projetos", html)

    def test_existing_web_templates_never_render_file_name_as_src(self):
        from pathlib import Path
        from django.conf import settings

        for folder in ("institutional", "auth", "emails"):
            for path in (settings.BASE_DIR / "templates" / folder).rglob("*.html"):
                with self.subTest(template=path.name):
                    self.assertNotIn('src="{{ identidade.logo }}"', path.read_text())

    @patch("plataforma.views.reverse", return_value="/convites/token/")
    def test_organization_sender_passes_branding_to_actual_html(self, reverse):
        _send_organization_invitation_email(self.request, self.invitation, "token")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://media.palaciomental.com.br/", mail.outbox[0].alternatives[0].content)
        self.assertIn("recipient@example.com", mail.outbox[0].body)

    @patch("plataforma.views.reverse", return_value="/convites/token/")
    def test_group_sender_passes_branding_to_actual_html(self, reverse):
        program = SimpleNamespace(nome="Programa", organizacao=self.organization)
        self.invitation.grupo = SimpleNamespace(nome="Grupo", turma=SimpleNamespace(programa=program))
        _send_group_invitation_email(self.request, self.invitation, "token")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://media.palaciomental.com.br/", mail.outbox[0].alternatives[0].content)
        self.assertIn("Programa", mail.outbox[0].alternatives[0].content)
