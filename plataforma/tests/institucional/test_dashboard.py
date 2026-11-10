from django.test import override_settings

from plataforma.management_metrics import management_distributions
from plataforma.models import DominioOrganizacao, MembroOrganizacao, Organizacao, Project
from .base import PortalInstitucionalBase


HOST = "camppg.palaciomental.com.br"


class ManagementDashboardTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        self.membership = MembroOrganizacao.objects.create(
            organizacao=self.organization, usuario=self.user, papel="gestor"
        )
        self.other = Organizacao.objects.create(slug="outro", nome="Outro", status="ativa")
        DominioOrganizacao.objects.create(
            organizacao=self.other, hostname="outro.palaciomental.com.br", principal=True
        )
        self.client.force_login(self.user)

    def test_distributions_count_only_current_tenant_without_private_content(self):
        Project.objects.create(owner=self.user, organizacao=self.organization,
                               title="Título privado que não deve sair", visibility="privado", status="ativo")
        Project.objects.create(owner=self.user, organizacao=self.organization,
                               title="Projeto concluído", visibility="publico", status="concluido")
        Project.objects.create(owner=self.user, organizacao=self.other,
                               title="Segredo de outra organização", visibility="privado", status="ativo")
        response = self.client.get("/gestao/", HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["management_charts"]["projects"]["values"], [0, 1, 0, 1])
        self.assertEqual(response.context["metricas"]["projetos"], 2)
        self.assertNotContains(response, "Título privado que não deve sair")
        self.assertNotContains(response, "Segredo de outra organização")
        self.assertContains(response, '<table class="tenant-chart-table"', count=2)
        self.assertContains(response, 'id="management-chart-data" type="application/json"')
        self.assertContains(response, "/static/vendor/chartjs-4.5.1/chart.umd.js")

    def test_only_active_memberships_of_current_tenant_are_counted(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.pm_staff,
                                         papel="professor", status="suspensa")
        MembroOrganizacao.objects.create(organizacao=self.other, usuario=self.user, papel="proprietario")
        data = management_distributions(self.organization)
        self.assertEqual(sum(data["members"]["values"]), 1)
        self.assertEqual(dict(zip(data["members"]["labels"], data["members"]["values"]))["Gestor"], 1)

    def test_member_and_professor_cannot_read_dashboard_by_direct_url(self):
        for role in ("membro", "professor"):
            with self.subTest(role=role):
                self.membership.papel = role
                self.membership.save(update_fields=["papel"])
                response = self.client.get("/gestao/", HTTP_HOST=HOST)
                self.assertEqual(response.status_code, 403)
                self.assertNotContains(response, "management-chart-data", status_code=403)

    def test_non_affiliated_and_global_host_cannot_read_dashboard(self):
        self.assertEqual(self.client.get("/gestao/", HTTP_HOST="outro.palaciomental.com.br").status_code, 403)
        self.assertEqual(self.client.get("/gestao/", HTTP_HOST="palaciomental.com.br").status_code, 404)

    @override_settings(REDIS_URL="")
    def test_empty_tenant_stays_usable_without_redis(self):
        response = self.client.get("/gestao/", HTTP_HOST=HOST)
        self.assertContains(response, "Nenhum projeto neste ambiente ainda.")
        self.assertEqual(response.context["management_charts"]["projects"]["values"], [0, 0, 0, 0])
        self.assertContains(response, "/gestao/identidade/")
        self.assertContains(response, "Identidade visual")
