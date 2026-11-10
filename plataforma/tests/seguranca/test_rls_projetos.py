"""RLS mínima em projetos: o banco isola mesmo se a aplicação esquecer o filtro."""

from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.utils import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from plataforma import rls
from plataforma.models import DominioOrganizacao, MembroOrganizacao, Organizacao, Project

User = get_user_model()

HOST_A = "camppg.palaciomental.com.br"
HOST_GLOBAL = "palaciomental.com.br"


def _role_flags():
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        return cursor.fetchone()


def _rls_efetiva():
    return connection.vendor == "postgresql" and not any(_role_flags())


@skipUnless(connection.vendor == "postgresql", "RLS exige PostgreSQL")
class CatalogoRLSTests(TestCase):
    def test_tabelas_protegidas_tem_rls_ativa_e_forcada(self):
        with connection.cursor() as cursor:
            for tabela in rls.PROTECTED_TABLES:
                cursor.execute(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = %s::regclass",
                    [tabela],
                )
                self.assertEqual(cursor.fetchone(), (True, True), tabela)
                cursor.execute("SELECT count(*) FROM pg_policy WHERE polrelid = %s::regclass", [tabela])
                self.assertGreaterEqual(cursor.fetchone()[0], 1, tabela)

    def test_role_da_aplicacao_nao_ignora_rls(self):
        """Falha quando a suíte roda com superusuário ou BYPASSRLS.

        Nesse caso a RLS não protege nada. Rode os testes com uma role comum
        (veja docs/arquitetura-multi-tenant-rls.md).
        """
        rolsuper, rolbypassrls = _role_flags()
        self.assertFalse(rolsuper, "a role do banco é superusuária: a RLS é ignorada")
        self.assertFalse(rolbypassrls, "a role do banco tem BYPASSRLS: a RLS é ignorada")


@override_settings(
    ALLOWED_HOSTS=["testserver", ".palaciomental.com.br"],
    PALACIO_BASE_DOMAIN="palaciomental.com.br",
    TENANT_RESERVED_HOSTS=["www", "api", "status", "admin", "app"],
)
class IsolamentoPorEscopoTests(TestCase):
    def setUp(self):
        if not _rls_efetiva():
            self.skipTest("role do banco ignora RLS")
        self.org_a = Organizacao.objects.create(slug="camppg", nome="CAMPPG", status=Organizacao.STATUS_ATIVA)
        self.org_b = Organizacao.objects.create(slug="outra", nome="Outra", status=Organizacao.STATUS_ATIVA)
        DominioOrganizacao.objects.create(organizacao=self.org_a, hostname=HOST_A, principal=True)
        self.autor = User.objects.create_user(username="autor", email="autor@example.com", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.org_a, usuario=self.autor, papel=MembroOrganizacao.PAPEL_MEMBRO)
        base = {"owner": self.autor, "direction": "Por quê", "category": "Educação", "visibility": Project.VISIBILITY_PUBLIC}
        self.pessoal = Project.objects.create(title="Pessoal", **base)
        self.de_a = Project.objects.create(title="Projeto A", organizacao=self.org_a, **base)
        self.de_b = Project.objects.create(title="Projeto B", organizacao=self.org_b, **base)

    def _visiveis(self):
        return set(Project.objects.values_list("pk", flat=True))

    def test_consulta_sem_filtro_respeita_o_escopo(self):
        with rls.rls_context(rls.MODE_TENANT, self.org_a.pk):
            self.assertEqual(self._visiveis(), {self.de_a.pk})
        with rls.rls_context(rls.MODE_GLOBAL):
            self.assertEqual(self._visiveis(), {self.pessoal.pk})
        with rls.rls_context(rls.MODE_DENY):
            self.assertEqual(self._visiveis(), set())
        with rls.system_context():
            self.assertEqual(self._visiveis(), {self.pessoal.pk, self.de_a.pk, self.de_b.pk})

    def test_tenant_sem_id_falha_fechado(self):
        with rls.rls_context(rls.MODE_TENANT, None):
            self.assertEqual(self._visiveis(), set())

    def test_nao_grava_projeto_em_outro_escopo(self):
        base = {"owner": self.autor, "direction": "x", "category": "y"}
        with rls.rls_context(rls.MODE_TENANT, self.org_a.pk):
            with self.assertRaises(DatabaseError), transaction.atomic():
                Project.objects.create(title="Intruso B", organizacao=self.org_b, **base)
            with self.assertRaises(DatabaseError), transaction.atomic():
                Project.objects.create(title="Intruso pessoal", **base)
        with rls.rls_context(rls.MODE_GLOBAL):
            with self.assertRaises(DatabaseError), transaction.atomic():
                Project.objects.create(title="Intruso A", organizacao=self.org_a, **base)

    def test_nao_move_projeto_para_outro_tenant(self):
        with rls.rls_context(rls.MODE_TENANT, self.org_a.pk):
            with self.assertRaises(DatabaseError), transaction.atomic():
                Project.objects.filter(pk=self.de_a.pk).update(organizacao=self.org_b)

    def test_update_e_delete_sem_filtro_nao_alcancam_outro_tenant(self):
        with rls.rls_context(rls.MODE_TENANT, self.org_a.pk):
            self.assertEqual(Project.objects.update(category="alterado"), 1)
            Project.objects.all().delete()
        with rls.system_context():
            self.assertTrue(Project.objects.filter(pk=self.de_b.pk, category="Educação").exists())
            self.assertTrue(Project.objects.filter(pk=self.pessoal.pk).exists())

    def test_mutacao_remover_filtro_da_aplicacao_continua_404(self):
        """Simula o erro humano: a view perde o filtro de organização."""
        self.client.force_login(self.autor)
        with mock.patch("plataforma.views._project_scope", lambda request: Project.objects.all()):
            for projeto in (self.de_b, self.pessoal):
                with self.subTest(projeto=projeto.title):
                    response = self.client.get(reverse("plataforma:project_detail", kwargs={"pk": projeto.pk}), HTTP_HOST=HOST_A)
                    self.assertEqual(response.status_code, 404)
            response = self.client.get(reverse("plataforma:project_detail", kwargs={"pk": self.de_a.pk}), HTTP_HOST=HOST_GLOBAL)
            self.assertEqual(response.status_code, 404)

    def test_contexto_e_restaurado_apos_a_requisicao(self):
        """Conexão reutilizada: o tenant de uma requisição não vaza para a próxima."""
        antes = rls.current_context()
        self.client.force_login(self.autor)
        self.client.get(reverse("plataforma:projects"), HTTP_HOST=HOST_A)
        self.assertEqual(rls.current_context(), antes)
        self.client.get(reverse("plataforma:projects"), HTTP_HOST=HOST_GLOBAL)
        self.assertEqual(rls.current_context(), antes)

    def test_titulo_repetido_entre_escopos_vira_erro_de_formulario(self):
        """Unicidade (autor, título) não pode virar erro 500 com a RLS."""
        from plataforma.forms import ProjectBasicsForm

        with rls.rls_context(rls.MODE_TENANT, self.org_a.pk):
            form = ProjectBasicsForm(data={"title": "Pessoal"}, owner=self.autor)
            form.is_valid()
            self.assertIn("title", form.errors)
