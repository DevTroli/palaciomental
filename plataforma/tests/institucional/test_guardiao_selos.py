from unittest.mock import patch

from django.urls import reverse
from django.utils.dateparse import parse_datetime

from plataforma.models import MembroOrganizacao, Project, ProjectLink
from .base import PortalInstitucionalBase


class SelosTenantTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user,
                                        papel=MembroOrganizacao.PAPEL_MEMBRO)
        self.project = Project.objects.create(owner=self.user, organizacao=self.organization,
                                              title="Institucional", direction="Contexto")
        self.link = ProjectLink.objects.create(project=self.project, label="Documento", url="https://example.com")
        self.client.force_login(self.user)

    @patch("plataforma.guardiao_consulta.consultar_links")
    def test_selo_no_tenant_e_isolamento_do_dominio_global(self, consult):
        consult.return_value = {self.link.pk: {"status": "QUEBRADO", "label": "Link quebrado",
                                               "checked_at": parse_datetime("2026-11-15T15:00:00Z")}}
        url = reverse("plataforma:project_detail", args=[self.project.pk])
        response = self.client.get(url, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(response, "Link quebrado")
        self.assertContains(response, "15/11/2026")
        consult.reset_mock()
        self.assertEqual(self.client.get(url, HTTP_HOST="palaciomental.com.br").status_code, 404)
        consult.assert_not_called()

    @patch("plataforma.guardiao_consulta.consultar_links")
    def test_caixa_nao_inclui_links_do_ambiente_global(self, consult):
        pessoal = Project.objects.create(owner=self.user, title="Pessoal", direction="Contexto")
        ProjectLink.objects.create(project=pessoal, label="Pessoal", url="https://example.org")
        consult.return_value = {self.link.pk: {"status": "QUEBRADO"}}
        response = self.client.get(reverse("plataforma:inbox"), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(response, "Links que precisam de atenção")
        self.assertEqual([link.pk for link in consult.call_args.args[0]], [self.link.pk])
