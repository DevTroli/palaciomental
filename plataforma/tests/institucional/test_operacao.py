from unittest.mock import patch
from urllib.parse import parse_qs

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, ProgrammingError
from django.test import TestCase

from plataforma.models import CollaborationRequest, MembroOrganizacao, Project, ProjectMember
from .base import PortalInstitucionalBase

HOST = "camppg.palaciomental.com.br"


class ReadinessTests(TestCase):
    def test_schema_atual_responde_ok(self):
        self.assertEqual(self.client.get("/pronto").status_code, 200)

    def test_migration_pendente_impede_readiness(self):
        with patch("plataforma.health.MigrationExecutor") as executor:
            executor.return_value.migration_plan.return_value = [object()]
            response = self.client.get("/pronto")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["reason"], "migrations_pending")

    def test_banco_indisponivel_retorna_503_sem_consultar_tenant(self):
        with patch("plataforma.health.connection.cursor", side_effect=OperationalError("offline")):
            response = self.client.get("/pronto")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["reason"], "database_unavailable")

    def test_rebuild_parcial_nao_substitui_ranking(self):
        with patch("plataforma.management.commands.rebuild_rankings.rebuild_rankings") as rebuild:
            with self.assertRaisesMessage(CommandError, "--project-ids não é suportado"):
                call_command("rebuild_rankings", project_ids=[1])
        rebuild.assert_not_called()


class OperacaoInstitucionalTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        self.membership = MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user)
        self.client.force_login(self.user)

    def test_falha_agenda_nao_impede_explorar_e_badge_degrada(self):
        with patch("plataforma.experience.EventoCalendario.objects.filter", side_effect=ProgrammingError("missing table")):
            self.assertEqual(self.client.get("/projetos/", HTTP_HOST=HOST).status_code, 200)
            response = self.client.get("/notificacoes/resumo/", HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 503)
        self.assertIsNone(response.json()["count"])

    def test_paginacao_preserva_filtros_sem_numero_da_pagina(self):
        response = self.client.get("/projetos/", {"aluno": self.user.username,
            "status": "ativo", "tag": "educação", "page": "2"}, HTTP_HOST=HOST)
        params = parse_qs(response.context["pagination_query"])
        self.assertEqual(params, {"aluno": [self.user.username], "status": ["ativo"], "tag": ["educação"]})

    def test_aprovacao_revalida_afiliacao_do_solicitante(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.pm_staff)
        project = Project.objects.create(owner=self.pm_staff, organizacao=self.organization,
            title="Projeto aberto", visibility=Project.VISIBILITY_PUBLIC)
        invitation = CollaborationRequest.objects.create(project=project, requester=self.user)
        self.membership.status = MembroOrganizacao.STATUS_SUSPENSA
        self.membership.save()
        self.client.force_login(self.pm_staff)
        response = self.client.post(f"/colaboracoes/{invitation.pk}/decidir/",
            {"decision": CollaborationRequest.ACCEPTED}, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ProjectMember.objects.filter(project=project, user=self.user).exists())
        self.assertTrue(CollaborationRequest.objects.filter(pk=invitation.pk).exists())
        self.membership.status = MembroOrganizacao.STATUS_ATIVA
        self.membership.save()
        response = self.client.post(f"/colaboracoes/{invitation.pk}/decidir/",
            {"decision": CollaborationRequest.ACCEPTED}, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProjectMember.objects.filter(project=project, user=self.user).exists())
