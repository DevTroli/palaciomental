from plataforma.models import IdentidadeOrganizacao, MembroOrganizacao

from .base import PortalInstitucionalBase


HOST = "camppg.palaciomental.com.br"


class RodapePersonalizadoTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        self.identity = IdentidadeOrganizacao.objects.create(organizacao=self.organization)
        self.membership = MembroOrganizacao.objects.create(
            organizacao=self.organization, usuario=self.user, papel="gestor"
        )
        self.client.force_login(self.user)

    def payload(self):
        return {
            "nome_exibicao": "CAMPPG",
            "slogan": "Aprender para transformar",
            "email_contato": "contato@example.org",
            "instagram_url": "https://instagram.com/camppg",
            "facebook_url": "https://facebook.com/camppg",
        }


    def test_unsafe_stored_links_are_not_rendered_and_slogan_is_escaped(self):
        self.identity.instagram_url = "javascript:alert(1)"
        self.identity.slogan = "<script>alert(1)</script>"
        self.identity.save()
        response = self.client.get("/", HTTP_HOST=HOST)
        self.assertNotContains(response, 'href="javascript:alert(1)"')
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
