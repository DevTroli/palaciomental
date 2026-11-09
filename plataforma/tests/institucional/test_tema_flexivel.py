from django.core.exceptions import ValidationError

from plataforma.branding import organization_branding
from plataforma.forms import IdentidadeOrganizacaoForm
from plataforma.models import IdentidadeOrganizacao, MembroOrganizacao
from plataforma.theme import brand_background, contrast, validate_theme
from .base import PortalInstitucionalBase

HOST = "camppg.palaciomental.com.br"


class TemaFlexivelTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        self.identity = IdentidadeOrganizacao.objects.create(
            organizacao=self.organization, cor_primaria="azul-sobrio",
            cor_destaque="verde-institucional", cor_fundo="bege-claro",
        )
        self.membership = MembroOrganizacao.objects.create(
            organizacao=self.organization, usuario=self.user, papel="gestor",
        )
        self.client.force_login(self.user)

    def payload(self):
        return {
            "nome_exibicao": "Meu campus", "cor_primaria": "azul-sobrio",
            "cor_destaque": "verde-institucional", "cor_fundo": "bege-claro",
            "theme_primary": "#abcdef", "theme_secondary": "#112233",
            "theme_accent": "#eedd00", "theme_background": "#000000",
            "theme_surface": "#ffffff",
        }

    def test_manager_saves_hex_and_keeps_legacy_columns(self):
        response = self.client.post("/gestao/identidade/", self.payload(), HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 302)
        self.identity.refresh_from_db()
        self.assertEqual(self.identity.tema["primary"], "#ABCDEF")
        self.assertEqual(self.identity.cor_primaria, "azul-sobrio")

    def test_owner_can_save(self):
        self.membership.papel = "proprietario"
        self.membership.save()
        response = self.client.post("/gestao/identidade/", self.payload(), HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 302)

    def test_other_roles_cannot_post_directly(self):
        for role in ("professor", "membro"):
            self.membership.papel = role
            self.membership.save()
            response = self.client.post("/gestao/identidade/", self.payload(), HTTP_HOST=HOST)
            self.assertEqual(response.status_code, 403)
        self.identity.refresh_from_db()
        self.assertEqual(self.identity.tema, {})

    def test_inactive_membership_cannot_change_identity(self):
        self.membership.status = "inativa"
        self.membership.save()
        self.client.post("/gestao/identidade/", self.payload(), HTTP_HOST=HOST)
        self.identity.refresh_from_db()
        self.assertEqual(self.identity.tema, {})

    def test_invalid_css_is_not_saved(self):
        payload = self.payload()
        payload["theme_primary"] = "#ffffff; background:url(x)"
        response = self.client.post("/gestao/identidade/", payload, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 200)
        self.identity.refresh_from_db()
        self.assertEqual(self.identity.tema, {})

    def test_invalid_identity_keeps_fields_and_errors_in_their_sections(self):
        payload = {**self.payload(), "email_contato": "invalido", "instagram_url": "https://instagram.com/camppg"}
        response = self.client.post("/gestao/identidade/", payload, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 200)
        self.assertIn("email_contato", response.context["form"].errors)
        self.assertContains(response, 'id="identity-brand"')
        self.assertContains(response, 'id="identity-colors"')
        self.assertContains(response, 'id="identity-footer"')
        self.assertContains(response, 'value="https://instagram.com/camppg"')
        self.identity.refresh_from_db()
        self.assertFalse(self.identity.instagram_url)

    def test_model_theme_validation(self):
        for value in ({"css": "body{}"}, {"primary": "red"}, {"primary": "#fff"}, {"primary": "#ffffffff"}, ["red"]):
            with self.assertRaises(ValidationError):
                validate_theme(value)

    def test_legacy_defaults_and_extreme_contrast(self):
        self.assertEqual(organization_branding(self.organization)["tenant_primary_color"], "#315A76")
        self.identity.tema = {"primary": "#FFFFFF", "surface": "#000000", "background": "#FDFDFD"}
        self.identity.save()
        self.organization.refresh_from_db()
        branding = organization_branding(self.organization)
        for color, text in (
            ("tenant_primary_color", "tenant_primary_text_color"),
            ("tenant_surface_color", "tenant_surface_text_color"),
            ("tenant_background_color", "tenant_background_text_color"),
        ):
            self.assertGreaterEqual(contrast(branding[color], branding[text]), 4.5)

    def test_brand_colors_remain_readable_with_light_and_dark_surfaces(self):
        for primary, surface, background in (
            ("#2C7DB3", "#FFFFFF", "#F3ECDF"),
            ("#FFFFFF", "#111111", "#111111"),
            ("#080808", "#080808", "#FFFFFF"),
            ("#F6E945", "#FFFFFF", "#FFFFFF"),
        ):
            with self.subTest(primary=primary, surface=surface, background=background):
                self.identity.tema = {"primary": primary, "surface": surface, "background": background}
                branding = organization_branding(self.organization)
                self.assertEqual(branding["tenant_primary_color"], primary)
                self.assertGreaterEqual(contrast(branding["tenant_solid_color"], "#FFFFFF"), 4.7)
                for color, text in (("tenant_selection_color", "tenant_selection_text_color"),
                                    ("tenant_surface_color", "tenant_surface_text_color")):
                    self.assertGreaterEqual(contrast(branding[color], branding[text]), 4.5)
                self.assertGreaterEqual(contrast(branding["tenant_selection_color"], surface), 3)
        self.assertEqual(brand_background("#112233"), "#112233")

    def test_theme_is_applied_to_home_management_and_login(self):
        self.identity.tema = {"primary": "#ABCDEF", "secondary": "#112233"}
        self.identity.save()
        for path in ("/", "/gestao/", "/gestao/identidade/", "/gestao/programas/", "/gestao/membros/"):
            response = self.client.get(path, HTTP_HOST=HOST)
            self.assertContains(response, "--tenant-primary:#ABCDEF")
        self.client.logout()
        self.assertContains(self.client.get("/entrar/", HTTP_HOST=HOST), "--tenant-primary:#ABCDEF")

    def test_friendly_upload_widget_hides_storage_key(self):
        self.identity.logo = self.logo_file()
        self.identity.save()
        form = IdentidadeOrganizacaoForm(instance=self.identity)
        html = str(form["logo"])
        self.assertIn("Ver imagem atual", html)
        self.assertNotIn(f">{self.identity.logo.name}<", html)
        self.assertIn("Remover imagem atual", html)

    def test_form_without_javascript_and_legacy_post_remain_valid(self):
        form = IdentidadeOrganizacaoForm(data=self.payload(), instance=self.identity)
        self.assertTrue(form.is_valid(), form.errors)
        legacy = {k: v for k, v in self.payload().items() if not k.startswith("theme_")}
        form = IdentidadeOrganizacaoForm(data=legacy, instance=self.identity)
        self.assertTrue(form.is_valid(), form.errors)
