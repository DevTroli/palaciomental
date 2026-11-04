from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from plataforma.models import (
    DominioOrganizacao,
    Grupo,
    MembroGrupo,
    MembroOrganizacao,
    MembroTurma,
    Organizacao,
    ProgramaInstitucional,
    Project,
    SolicitacaoGrupo,
    SolicitacaoTurma,
    Turma,
)


User = get_user_model()

HOST_A = "camppg.palaciomental.com.br"
HOST_B = "outra.palaciomental.com.br"
HOST_GLOBAL = "palaciomental.com.br"


@override_settings(
    ALLOWED_HOSTS=["testserver", ".palaciomental.com.br"],
    PALACIO_BASE_DOMAIN="palaciomental.com.br",
    TENANT_RESERVED_HOSTS=["www", "api", "status", "admin", "app"],
)
class DecisaoDeSolicitacaoEntreTenantsTests(TestCase):
    """PM-01 e PM-02: decidir solicitacoes exige o tenant dono do objeto."""

    def setUp(self):
        self.org_a = Organizacao.objects.create(slug="camppg", nome="CAMPPG", status=Organizacao.STATUS_ATIVA)
        self.org_b = Organizacao.objects.create(slug="outra", nome="Outra organizacao", status=Organizacao.STATUS_ATIVA)
        DominioOrganizacao.objects.create(organizacao=self.org_a, hostname=HOST_A, principal=True)
        DominioOrganizacao.objects.create(organizacao=self.org_b, hostname=HOST_B, principal=True)

        self.gestor_a = User.objects.create_user(username="gestor-a", email="gestor-a@example.com", password="Senha-forte-123")
        self.gestor_b = User.objects.create_user(username="gestor-b", email="gestor-b@example.com", password="Senha-forte-123")
        self.professor_b = User.objects.create_user(username="professor-b", email="professor-b@example.com", password="Senha-forte-123")
        self.solicitante = User.objects.create_user(username="solicitante-b", email="solicitante-b@example.com", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.org_a, usuario=self.gestor_a, papel=MembroOrganizacao.PAPEL_GESTOR)
        MembroOrganizacao.objects.create(organizacao=self.org_b, usuario=self.gestor_b, papel=MembroOrganizacao.PAPEL_GESTOR)
        MembroOrganizacao.objects.create(organizacao=self.org_b, usuario=self.professor_b, papel=MembroOrganizacao.PAPEL_PROFESSOR)
        MembroOrganizacao.objects.create(organizacao=self.org_b, usuario=self.solicitante, papel=MembroOrganizacao.PAPEL_MEMBRO)

        programa = ProgramaInstitucional.objects.create(
            organizacao=self.org_b,
            nome="Programa B",
            slug="programa-b",
            status=ProgramaInstitucional.STATUS_PUBLICADO,
            criado_por=self.gestor_b,
        )
        self.turma_b = Turma.objects.create(
            programa=programa,
            nome="Turma B",
            criado_por=self.gestor_b,
            professor_responsavel=self.professor_b,
            politica_participacao=Turma.POLITICA_APROVACAO,
        )
        self.grupo_b = Grupo.objects.create(turma=self.turma_b, nome="Grupo B", criado_por=self.gestor_b)
        self.solicitacao_turma = SolicitacaoTurma.objects.create(
            turma=self.turma_b, usuario=self.solicitante, mensagem="Quero participar."
        )
        self.solicitacao_grupo = SolicitacaoGrupo.objects.create(
            grupo=self.grupo_b, usuario=self.solicitante, mensagem="Quero participar."
        )

    def url_turma(self):
        return reverse("plataforma:institutional_class_request_decide", kwargs={"request_id": self.solicitacao_turma.pk})

    def url_grupo(self):
        return reverse("plataforma:institutional_group_request_decide", kwargs={"request_id": self.solicitacao_grupo.pk})

    def assert_turma_intacta(self):
        self.solicitacao_turma.refresh_from_db()
        self.assertEqual(self.solicitacao_turma.status, SolicitacaoTurma.STATUS_PENDENTE)
        self.assertFalse(MembroTurma.objects.filter(turma=self.turma_b, usuario=self.solicitante).exists())

    def assert_grupo_intacto(self):
        self.solicitacao_grupo.refresh_from_db()
        self.assertEqual(self.solicitacao_grupo.status, SolicitacaoGrupo.STATUS_PENDENTE)
        self.assertFalse(MembroGrupo.objects.filter(grupo=self.grupo_b, usuario=self.solicitante).exists())

    def test_pm01_gestor_de_outro_tenant_nao_decide_solicitacao_de_turma(self):
        self.client.force_login(self.gestor_a)
        response = self.client.post(self.url_turma(), {"acao": "aprovar"}, HTTP_HOST=HOST_A)
        self.assertEqual(response.status_code, 404)
        self.assert_turma_intacta()

    def test_pm01_host_global_nao_decide_solicitacao_de_turma_nem_para_professor(self):
        self.client.force_login(self.professor_b)
        response = self.client.post(self.url_turma(), {"acao": "aprovar"}, HTTP_HOST=HOST_GLOBAL)
        self.assertEqual(response.status_code, 404)
        self.assert_turma_intacta()

    def test_pm01_gestor_do_proprio_tenant_decide_solicitacao_de_turma(self):
        self.client.force_login(self.gestor_b)
        response = self.client.post(self.url_turma(), {"acao": "aprovar"}, HTTP_HOST=HOST_B)
        self.assertEqual(response.status_code, 302)
        self.solicitacao_turma.refresh_from_db()
        self.assertEqual(self.solicitacao_turma.status, SolicitacaoTurma.STATUS_APROVADA)
        self.assertTrue(MembroTurma.objects.filter(turma=self.turma_b, usuario=self.solicitante).exists())

    def test_pm02_gestor_de_outro_tenant_nao_decide_solicitacao_de_grupo(self):
        self.client.force_login(self.gestor_a)
        response = self.client.post(self.url_grupo(), {"acao": "aprovar"}, HTTP_HOST=HOST_A)
        self.assertEqual(response.status_code, 404)
        self.assert_grupo_intacto()

    def test_pm02_host_global_nao_decide_solicitacao_de_grupo(self):
        self.client.force_login(self.gestor_b)
        response = self.client.post(self.url_grupo(), {"acao": "aprovar"}, HTTP_HOST=HOST_GLOBAL)
        self.assertEqual(response.status_code, 404)
        self.assert_grupo_intacto()

    def test_pm02_gestor_do_proprio_tenant_decide_solicitacao_de_grupo(self):
        self.client.force_login(self.gestor_b)
        response = self.client.post(self.url_grupo(), {"acao": "aprovar"}, HTTP_HOST=HOST_B)
        self.assertEqual(response.status_code, 302)
        self.solicitacao_grupo.refresh_from_db()
        self.assertEqual(self.solicitacao_grupo.status, SolicitacaoGrupo.STATUS_APROVADA)
        self.assertTrue(MembroGrupo.objects.filter(grupo=self.grupo_b, usuario=self.solicitante).exists())


@override_settings(
    ALLOWED_HOSTS=["testserver", ".palaciomental.com.br"],
    PALACIO_BASE_DOMAIN="palaciomental.com.br",
    TENANT_RESERVED_HOSTS=["www", "api", "status", "admin", "app"],
)
class RedirectsAbertosTests(TestCase):
    """PM-03 e PM-04: o parametro next so aceita destinos do proprio host."""

    NEXT_EXTERNOS = ["https://evil.example/", "//evil.example/", "javascript:alert(1)"]

    def setUp(self):
        self.user = User.objects.create_user(username="autor-global", email="autor@example.com", password="Senha-forte-123")

    def login_com_next(self, next_url):
        url = f"{reverse('plataforma:login')}?next={quote(next_url, safe='')}"
        return self.client.post(
            url,
            {"username": "autor-global", "password": "Senha-forte-123"},
            HTTP_HOST=HOST_GLOBAL,
        )

    def test_pm03_login_global_ignora_next_externo(self):
        for next_url in self.NEXT_EXTERNOS:
            with self.subTest(next_url=next_url):
                self.client.logout()
                response = self.login_com_next(next_url)
                self.assertRedirects(response, reverse("plataforma:projects"), fetch_redirect_response=False)

    def test_pm03_login_global_aceita_next_interno(self):
        destino = reverse("plataforma:profile", kwargs={"username": "autor-global"})
        response = self.login_com_next(destino)
        self.assertRedirects(response, destino, fetch_redirect_response=False)

    def test_pm04_voto_ignora_next_externo(self):
        projeto = Project.objects.create(
            owner=self.user,
            title="Projeto global publico",
            direction="Teste",
            category="Teste",
            visibility=Project.VISIBILITY_PUBLIC,
        )
        url = reverse("plataforma:toggle_vote", kwargs={"pk": projeto.pk})
        padrao = reverse("plataforma:project_detail", kwargs={"pk": projeto.pk})
        self.client.force_login(self.user)
        for next_url in self.NEXT_EXTERNOS:
            with self.subTest(next_url=next_url):
                response = self.client.post(url, {"next": next_url}, HTTP_HOST=HOST_GLOBAL)
                self.assertRedirects(response, padrao, fetch_redirect_response=False)

    def test_pm04_voto_aceita_next_interno(self):
        projeto = Project.objects.create(
            owner=self.user,
            title="Projeto global publico",
            direction="Teste",
            category="Teste",
            visibility=Project.VISIBILITY_PUBLIC,
        )
        url = reverse("plataforma:toggle_vote", kwargs={"pk": projeto.pk})
        destino = reverse("plataforma:projects")
        self.client.force_login(self.user)
        response = self.client.post(url, {"next": destino}, HTTP_HOST=HOST_GLOBAL)
        self.assertRedirects(response, destino, fetch_redirect_response=False)
