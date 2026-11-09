from plataforma.models import DominioOrganizacao, IdentidadeOrganizacao, MembroOrganizacao, Organizacao

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
            "slogan_rodape": "Aprender para transformar",
            "email_contato": "contato@example.org",
            "instagram_url": "https://instagram.com/camppg",
            "facebook_url": "https://facebook.com/camppg",
        }

    def test_manager_and_owner_can_save_and_members_can_see_footer(self):
        for role in ("gestor", "proprietario"):
            self.membership.papel = role
            self.membership.save(update_fields=["papel"])
            response = self.client.post("/gestao/identidade/", self.payload(), HTTP_HOST=HOST)
            self.assertEqual(response.status_code, 302)
        self.identity.refresh_from_db()
        self.assertEqual(self.identity.slogan_rodape, "Aprender para transformar")
        self.membership.papel = "membro"
        self.membership.save(update_fields=["papel"])
        response = self.client.get("/", HTTP_HOST=HOST)
        for expected in ("Aprender para transformar", "contato@example.org", "mailto:contato%40example.org",
                         "https://instagram.com/camppg", "https://facebook.com/camppg",
                         "Status do sistema", "Dê continuidade às suas ideias."):
            self.assertContains(response, expected)
        self.assertContains(response, 'aria-label="Facebook de CAMPPG"')

    def test_non_managers_cannot_edit_and_invalid_values_are_rejected(self):
        for role in ("membro", "professor"):
            self.membership.papel = role
            self.membership.save(update_fields=["papel"])
            self.assertEqual(self.client.post("/gestao/identidade/", self.payload(), HTTP_HOST=HOST).status_code, 403)
        self.membership.papel = "gestor"
        self.membership.save(update_fields=["papel"])
        for field, invalid in (("instagram_url", "javascript:alert(1)"), ("email_contato", "invalido")):
            payload = {**self.payload(), field: invalid}
            response = self.client.post("/gestao/identidade/", payload, HTTP_HOST=HOST)
            self.assertEqual(response.status_code, 200)
            self.assertIn(field, response.context["form"].errors)
        self.identity.refresh_from_db()
        self.assertFalse(self.identity.email_contato)

    def test_footer_is_scoped_to_organization_and_handles_empty_fields(self):
        self.client.post("/gestao/identidade/", self.payload(), HTTP_HOST=HOST)
        other = Organizacao.objects.create(nome="Outra organização", slug="outra", status="ativa")
        DominioOrganizacao.objects.create(organizacao=other, hostname="outra.palaciomental.com.br", principal=True)
        IdentidadeOrganizacao.objects.create(organizacao=other, slogan_rodape="Outro ambiente")
        MembroOrganizacao.objects.create(organizacao=other, usuario=self.user)
        response = self.client.get("/", HTTP_HOST="outra.palaciomental.com.br")
        self.assertContains(response, "Outro ambiente")
        self.assertNotContains(response, "contato@example.org")
        self.assertNotContains(response, "instagram.com/camppg")
        self.assertContains(response, "Outra organização")
        self.client.post("/gestao/identidade/", {"nome_exibicao": "CAMPPG"}, HTTP_HOST=HOST)
        response = self.client.get("/", HTTP_HOST=HOST)
        self.assertContains(response, "Seu ambiente de projetos e conexões.")
        self.assertNotContains(response, "mailto:contato%40example.org")

    def test_unsafe_stored_links_are_not_rendered_and_slogan_is_escaped(self):
        self.identity.instagram_url = "javascript:alert(1)"
        self.identity.slogan_rodape = "<script>alert(1)</script>"
        self.identity.save()
        response = self.client.get("/", HTTP_HOST=HOST)
        self.assertNotContains(response, 'href="javascript:alert(1)"')
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
