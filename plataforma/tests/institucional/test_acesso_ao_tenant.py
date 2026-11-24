from django.contrib.auth import get_user_model
from django.urls import reverse

from plataforma.models import MembroOrganizacao, Organizacao, ProgramaInstitucional, Project


User = get_user_model()


from .base import PortalInstitucionalBase


class AcessoAoTenantTests(PortalInstitucionalBase):

    def test_tenant_requires_authentication(self):
        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")

        self.assertRedirects(
            response,
            f"{reverse('plataforma:login')}?next=/",
            fetch_redirect_response=False,
        )


    def test_tenant_registration_is_closed_and_contextualized(self):
        response = self.client.get(
            reverse("plataforma:register"),
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Cadastro fechado", status_code=403)
        self.assertContains(response, "somente por convite", status_code=403)

    def test_authenticated_user_without_affiliation_is_forbidden(self):
        self.client.force_login(self.user)

        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "afiliação ativa", status_code=403)

    def test_active_affiliation_can_enter_resolved_tenant(self):
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        self.client.force_login(self.user)

        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Projetos da comunidade")
        self.assertEqual(response.context["organizacao"], self.organization)
        self.assertContains(response, "Ranking de projetos")

    def test_tenant_home_shows_only_published_current_tenant_content(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa CAMPPG",
            slug="programa-camppg-home",
            status=ProgramaInstitucional.STATUS_PUBLICADO,
            criado_por=self.user,
        )
        self.make_group(programa, "Grupo CAMPPG")
        Project.objects.create(
            owner=self.user,
            organizacao=self.organization,
            title="Projeto CAMPPG publicado",
            direction="Projeto dentro do tenant",
            category="Educação",
            visibility=Project.VISIBILITY_PUBLIC,
        )
        other = Organizacao.objects.create(slug="outra", nome="Outra organização", status=Organizacao.STATUS_ATIVA)
        Project.objects.create(
            owner=self.user,
            organizacao=other,
            title="Projeto de outro tenant",
            direction="Não deve aparecer",
            category="Outro",
            visibility=Project.VISIBILITY_PUBLIC,
        )
        self.client.force_login(self.user)
        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Programa CAMPPG")
        self.assertContains(response, "Projeto CAMPPG publicado")

    def test_tenant_shell_has_skip_link_navigation_footer_and_no_global_vitrine_link(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        self.client.force_login(self.user)
        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pular para o conteúdo principal")
        self.assertContains(response, 'aria-label="Navegação do ambiente"')
        self.assertContains(response, "Meus Projetos")
        self.assertContains(response, 'href="http://palaciomental.com.br/" aria-label="Ir para a página inicial do Palácio Mental"')
        self.assertContains(response, "Dê continuidade às suas ideias.")
        footer = response.content.decode().split('<footer class="camp-footer', 1)[1].split('</footer>', 1)[0]
        self.assertNotIn("Início do ambiente", footer)
        self.assertNotIn("Meu espaço pessoal", footer)
        self.assertNotIn("Status do sistema", footer)
        self.assertContains(response, "tenant-footer")
        self.assertNotContains(response, "Vitrine global")
        self.assertNotContains(response, "Projeto de outro tenant")


    def test_login_redirects_manager_to_management_and_member_to_tenant_home(self):
        manager = User.objects.create_user(username="login-gestor", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=manager, papel=MembroOrganizacao.PAPEL_GESTOR)
        response = self.client.post(
            reverse("plataforma:login"),
            {"username": "login-gestor", "password": "Senha-forte-123"},
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertRedirects(response, reverse("plataforma:institutional_management"), fetch_redirect_response=False)

        self.client.logout()
        member = User.objects.create_user(username="login-membro", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=member, papel=MembroOrganizacao.PAPEL_MEMBRO)
        response = self.client.post(
            reverse("plataforma:login"),
            {"username": "login-membro", "password": "Senha-forte-123"},
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertRedirects(response, reverse("core:index"), fetch_redirect_response=False)


    def test_regular_member_cannot_update_tenant_identity(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        self.client.force_login(self.user)
        response = self.client.get(reverse("plataforma:institutional_identity"), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 403)
