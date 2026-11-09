from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse

from plataforma.models import (
    CollaborationRequest, DominioOrganizacao, IdentidadeOrganizacao,
    MembroOrganizacao, Notification, Organizacao, Project, ProjectMember,
)
from plataforma.navigation import project_notification_url

from .base import PortalInstitucionalBase


HOST = "camppg.palaciomental.com.br"
GLOBAL = "palaciomental.com.br"


class FluxoProjetosTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        MembroOrganizacao.objects.create(
            organizacao=self.organization, usuario=self.user,
            papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        IdentidadeOrganizacao.objects.create(
            organizacao=self.organization, nome_exibicao="Instituição de teste",
        )
        self.client.force_login(self.user)
        self.project = Project.objects.create(
            owner=self.user, organizacao=self.organization,
            title="Privado institucional", direction="Contexto",
            visibility=Project.VISIBILITY_PRIVATE,
        )

    def test_home_separa_criacao_institucional_e_espaco_pessoal(self):
        response = self.client.get("/", HTTP_HOST=HOST, secure=True)
        self.assertContains(response, 'href="/projetos/novo/"')
        self.assertContains(response, 'href="https://palaciomental.com.br/" aria-label="Ir para a página inicial do Palácio Mental"')
        self.assertContains(response, "Meus Projetos")

    def test_fluxo_criar_salvar_contexto_reabrir_e_editar_sem_sair_do_tenant(self):
        response = self.client.post(reverse("plataforma:project_create"), {
            "title": "Fluxo completo", "direction": "Teste",
            "status": "ideia", "visibility": "privado", "tipo_projeto": "autonomo",
        }, HTTP_HOST=HOST)
        project = Project.objects.get(title="Fluxo completo")
        context_url = reverse("plataforma:project_context", args=[project.pk])
        detail_url = reverse("plataforma:project_detail", args=[project.pk])
        self.assertRedirects(response, context_url, fetch_redirect_response=False)
        self.assertEqual(self.client.get(context_url, HTTP_HOST=HOST).status_code, 200)
        response = self.client.post(context_url, {
            "category": "Homologação", "tags": "teste", "visibility": "privado",
            "links-TOTAL_FORMS": "0", "links-INITIAL_FORMS": "0",
            "links-MIN_NUM_FORMS": "0", "links-MAX_NUM_FORMS": "12",
        }, HTTP_HOST=HOST)
        self.assertRedirects(response, detail_url, fetch_redirect_response=False)
        detail = self.client.get(detail_url, HTTP_HOST=HOST)
        self.assertContains(detail, "Fluxo completo")
        self.assertContains(detail, 'href="/perfil/participante/"')
        profile = self.client.get(reverse("plataforma:profile", args=[self.user.username]), HTTP_HOST=HOST)
        self.assertContains(profile, f'href="{detail_url}"')
        response = self.client.post(reverse("plataforma:project_edit", args=[project.pk]), {
            "title": "Fluxo revisado", "direction": "Teste revisado",
            "status": "ativo", "visibility": "privado", "tipo_projeto": "autonomo",
        }, HTTP_HOST=HOST)
        self.assertRedirects(response, detail_url, fetch_redirect_response=False)
        project.refresh_from_db()
        self.assertEqual(project.title, "Fluxo revisado")
        self.assertEqual(project.organizacao_id, self.organization.pk)
        self.assertEqual(self.client.get(detail_url, HTTP_HOST=GLOBAL).status_code, 404)

    def test_perfil_do_tenant_mostra_privados_do_autor_sem_projetos_pessoais(self):
        Project.objects.create(owner=self.user, title="Somente pessoal", direction="Teste")
        response = self.client.get(reverse("plataforma:profile", args=[self.user.username]), HTTP_HOST=HOST)
        self.assertContains(response, "Privado institucional")
        self.assertNotContains(response, "Somente pessoal")
        self.assertContains(response, "Projetos institucionais")
        self.assertNotContains(response, "Projetos autorais")

    def test_header_de_todas_as_telas_de_projeto_preserva_identidade(self):
        paths = [
            reverse("plataforma:projects"),
            reverse("plataforma:profile", args=[self.user.username]),
            reverse("plataforma:project_create"),
            reverse("plataforma:project_detail", args=[self.project.pk]),
            reverse("plataforma:project_edit", args=[self.project.pk]),
            reverse("plataforma:project_context", args=[self.project.pk]),
        ]
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST=HOST)
                self.assertContains(response, 'class="camp-topbar"')
                self.assertNotContains(response, 'class="mvp-brand"')
                self.assertContains(response, "Instituição de teste")
                self.assertContains(response, 'id="main-content"')
                header = response.content.decode().split('<header class="camp-topbar">', 1)[1].split("</header>", 1)[0]
                self.assertNotIn("mind_palace_logo.png", header)

    def test_global_mantem_marca_e_criacao_pessoal(self):
        response = self.client.get(reverse("plataforma:profile", args=[self.user.username]), HTTP_HOST=GLOBAL)
        self.assertContains(response, 'class="mvp-brand"')
        self.assertContains(response, "Projetos autorais")
        self.assertNotContains(response, "Privado institucional")

    def test_notificacoes_usam_host_do_projeto_e_nao_host_do_cliente(self):
        request = RequestFactory().get("/", HTTP_HOST="outra.palaciomental.com.br", secure=True)
        expected = f"https://{HOST}/projetos/{self.project.pk}/"
        self.assertEqual(project_notification_url(request, self.project), expected)
        personal = Project.objects.create(owner=self.user, title="Pessoal", direction="Teste")
        self.assertEqual(
            project_notification_url(request, personal),
            f"https://{GLOBAL}/projetos/{personal.pk}/",
        )

    def test_solicitacao_e_decisao_guardam_url_canonica_institucional(self):
        other = get_user_model().objects.create_user(username="colaborador")
        MembroOrganizacao.objects.create(
            organizacao=self.organization, usuario=other, papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        self.project.visibility = Project.VISIBILITY_PUBLIC
        self.project.save()
        self.client.force_login(other)
        response = self.client.post(
            reverse("plataforma:request_collaboration", args=[self.project.pk]),
            {"message": "Quero colaborar"}, HTTP_HOST=HOST, secure=True,
        )
        self.assertEqual(response.status_code, 302)
        expected = f"https://{HOST}/projetos/{self.project.pk}/"
        self.assertEqual(Notification.objects.get(recipient=self.user).url, expected)
        collaboration = CollaborationRequest.objects.get(project=self.project)
        self.client.force_login(self.user)
        inbox = self.client.get(reverse("plataforma:inbox"), HTTP_HOST=HOST, secure=True)
        self.assertContains(inbox, reverse("plataforma:decide_collaboration", args=[collaboration.pk]))
        self.assertContains(inbox, "Quero colaborar")
        response = self.client.post(
            reverse("plataforma:decide_collaboration", args=[collaboration.pk]),
            {"decision": CollaborationRequest.ACCEPTED}, HTTP_HOST=HOST, secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Notification.objects.get(recipient=other).url, expected)

    def test_workspace_only_for_members_and_no_duplicate_collaboration_action(self):
        other = get_user_model().objects.create_user(username="membro-equipe")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=other)
        self.project.visibility = Project.VISIBILITY_PUBLIC
        self.project.seeking_collaborators = True
        self.project.save()
        self.client.force_login(other)
        url = reverse("plataforma:project_detail", args=[self.project.pk])
        self.assertNotContains(self.client.get(url, HTTP_HOST=HOST), "Você colabora neste projeto")
        ProjectMember.objects.create(project=self.project, user=other)
        response = self.client.get(url, HTTP_HOST=HOST)
        self.assertContains(response, "Você colabora neste projeto")
        self.assertNotContains(response, "Tenho interesse")
        public_profile = self.client.get(reverse("plataforma:profile", args=[self.user.username]), HTTP_HOST=HOST)
        self.assertContains(public_profile, "tenant-member.css")
        self.assertNotContains(public_profile, "Abrir meu espaço pessoal")

    def test_restricted_share_requires_token_and_active_tenant_affiliation(self):
        self.project.visibility = Project.VISIBILITY_RESTRICTED
        self.project.save(update_fields=["visibility"])
        url = reverse("plataforma:project_detail", args=[self.project.pk])
        response = self.client.get(url, HTTP_HOST=HOST, secure=True)
        self.assertContains(response, f"?access={self.project.access_token}")
        outsider = get_user_model().objects.create_user(username="sem-afiliacao")
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(url + f"?access={self.project.access_token}", HTTP_HOST=HOST).status_code, 403)
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=outsider)
        self.assertEqual(self.client.get(url, HTTP_HOST=HOST).status_code, 404)
        self.assertEqual(self.client.get(url + "?access=invalido", HTTP_HOST=HOST).status_code, 404)
        self.assertEqual(self.client.get(url + f"?access={self.project.access_token}", HTTP_HOST=HOST).status_code, 200)

    def test_outro_tenant_continua_sem_acesso(self):
        other = Organizacao.objects.create(slug="outra", nome="Outra", status=Organizacao.STATUS_ATIVA)
        DominioOrganizacao.objects.create(organizacao=other, hostname="outra.palaciomental.com.br", principal=True)
        MembroOrganizacao.objects.create(organizacao=other, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        response = self.client.get(
            reverse("plataforma:project_detail", args=[self.project.pk]),
            HTTP_HOST="outra.palaciomental.com.br",
        )
        self.assertEqual(response.status_code, 404)
