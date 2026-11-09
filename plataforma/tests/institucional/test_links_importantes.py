from plataforma.models import IdentidadeOrganizacao, MembroOrganizacao
from .base import PortalInstitucionalBase

HOST = "camppg.palaciomental.com.br"


class LinksImportantesTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        self.identity = IdentidadeOrganizacao.objects.create(organizacao=self.organization)
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel="gestor")
        self.client.force_login(self.user)

    def test_three_links_are_saved_and_displayed(self):
        data = {"nome_exibicao": "CAMP", "site_oficial": "https://example.org/",
                "link_1_titulo": "Site", "link_2_titulo": "Inscrições", "link_2_url": "https://example.org/inscricoes",
                "link_3_titulo": "Atendimento", "link_3_url": "https://example.org/contato"}
        self.assertEqual(self.client.post("/gestao/identidade/", data, HTTP_HOST=HOST).status_code, 302)
        response = self.client.get("/", HTTP_HOST=HOST)
        for value in ("Inscrições", "Atendimento", "https://example.org/contato"):
            self.assertContains(response, value)

    def test_invalid_or_incomplete_link_is_rejected(self):
        response = self.client.post("/gestao/identidade/", {"nome_exibicao": "CAMP", "link_2_titulo": "Teste", "link_2_url": "javascript:alert(1)"}, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 200)
        self.assertIn("link_2_url", response.context["form"].errors)
