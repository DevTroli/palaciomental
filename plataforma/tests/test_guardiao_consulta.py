import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.dateparse import parse_datetime

from plataforma.guardiao_consulta import consultar_links, contar_atencao, marcar_links
from plataforma.models import GuardiaoLinkPendente, Project, ProjectLink


@override_settings(GUARDIAO_API_URL="https://guardiao.example", GUARDIAO_SERVICE_TOKEN="teste")
class ConsultaGuardiaoTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="dono")
        self.other = get_user_model().objects.create_user(username="outro")
        self.project = Project.objects.create(owner=self.owner, title="Teste", direction="Contexto", visibility=Project.VISIBILITY_PRIVATE)
        self.link = ProjectLink.objects.create(project=self.project, label="Link", url="https://example.com")
        GuardiaoLinkPendente.objects.all().delete()

    @patch("plataforma.guardiao_consulta.build_opener")
    def test_cinco_estados_e_data(self, opener):
        response = opener.return_value.open.return_value.__enter__.return_value
        for status, tone in (("ACESSIVEL", "success"), ("REDIRECIONADO", "neutral"),
                             ("REQUER_LOGIN", "neutral"), ("QUEBRADO", "warning"), ("SEM_RESPOSTA", "warning")):
            response.read.return_value = json.dumps([{"link_id": self.link.pk, "status": status, "checked_at": "2026-11-15T12:00:00Z"}]).encode()
            result = consultar_links([self.link])
            self.assertEqual(result[self.link.pk]["status"], status)
            self.assertEqual(result[self.link.pk]["tone"], tone)
            self.assertIsNotNone(result[self.link.pk]["checked_at"])

    @patch("plataforma.guardiao_consulta.build_opener")
    def test_pendente_nao_exibe_resultado_antigo(self, opener):
        GuardiaoLinkPendente.objects.create(link_id=self.link.pk)
        opener.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps([
            {"link_id": self.link.pk, "status": "ACESSIVEL", "checked_at": "2026-11-15T12:00:00Z"}]).encode()
        self.assertEqual(consultar_links([self.link]), {})

    @patch("plataforma.guardiao_consulta.build_opener")
    def test_quebra_so_e_confirmada_apos_tres_ciclos(self, opener):
        response = opener.return_value.open.return_value.__enter__.return_value
        for failures, label, tone in ((1, "Possível quebra", "warning"), (2, "Possível quebra", "warning"), (3, "Link quebrado", "danger")):
            response.read.return_value = json.dumps([{"link_id": self.link.pk, "status": "QUEBRADO",
                                                       "checked_at": "2026-11-15T12:00:00Z",
                                                       "failed_cycles": failures}]).encode()
            result = consultar_links([self.link])[self.link.pk]
            self.assertEqual(result["label"], label)
            self.assertEqual(result["tone"], tone)

    @patch("plataforma.guardiao_consulta.build_opener")
    def test_indisponibilidade_mantem_link_legivel(self, opener):
        opener.return_value.open.side_effect = URLError("indisponível")
        self.assertIsNone(consultar_links([self.link]))
        self.assertTrue(marcar_links([self.link])[0].guardiao_indisponivel)

    @patch("plataforma.guardiao_consulta.build_opener")
    def test_api_antiga_registra_http_sem_dados_sensiveis(self, opener):
        opener.return_value.open.side_effect = HTTPError("https://segredo.example", 404, "erro", {}, None)
        with self.assertLogs("plataforma.guardiao_consulta", level="WARNING") as logs:
            self.assertIsNone(consultar_links([self.link]))
        self.assertIn("HTTP 404", logs.output[0])
        self.assertNotIn("segredo", logs.output[0])

    @patch("plataforma.guardiao_consulta.consultar_links")
    def test_contagem_so_inclui_links_do_autor_no_ambiente(self, consult):
        other_project = Project.objects.create(owner=self.other, title="Outro", direction="Contexto")
        ProjectLink.objects.create(project=other_project, label="Outro", url="https://example.org")
        consult.return_value = {self.link.pk: {"status": "QUEBRADO"}}
        self.assertEqual(contar_atencao(self.owner, None), 1)
        self.assertEqual([x.pk for x in consult.call_args.args[0]], [self.link.pk])

    @patch("plataforma.guardiao_consulta.marcar_links")
    def test_projeto_privado_negado_antes_de_consultar(self, mark):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("plataforma:project_detail", args=[self.project.pk])).status_code, 404)
        mark.assert_not_called()

    @patch("plataforma.guardiao_consulta.consultar_links")
    def test_detalhe_exibe_selo_e_data_sem_depender_de_cor(self, consult):
        self.client.force_login(self.owner)
        consult.return_value = {self.link.pk: {"status": "QUEBRADO", "label": "Link quebrado",
                                               "checked_at": parse_datetime("2026-11-15T15:00:00Z")}}
        response = self.client.get(reverse("plataforma:project_detail", args=[self.project.pk]))
        self.assertContains(response, "Link quebrado")
        self.assertContains(response, "15/11/2026")
        consult.return_value = None
        response = self.client.get(reverse("plataforma:project_detail", args=[self.project.pk]))
        self.assertContains(response, "Verificação indisponível")
        self.assertContains(response, "https://example.com")
