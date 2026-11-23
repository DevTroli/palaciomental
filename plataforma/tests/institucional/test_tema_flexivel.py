from plataforma.models import IdentidadeOrganizacao, MembroOrganizacao
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


    def test_other_roles_cannot_post_directly(self):
        for role in ("professor", "membro"):
            self.membership.papel = role
            self.membership.save()
            response = self.client.post("/gestao/identidade/", self.payload(), HTTP_HOST=HOST)
            self.assertEqual(response.status_code, 403)
        self.identity.refresh_from_db()
        self.assertEqual(self.identity.tema, {})


    def test_invalid_css_is_not_saved(self):
        payload = self.payload()
        payload["theme_primary"] = "#ffffff; background:url(x)"
        response = self.client.post("/gestao/identidade/", payload, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 200)
        self.identity.refresh_from_db()
        self.assertEqual(self.identity.tema, {})
