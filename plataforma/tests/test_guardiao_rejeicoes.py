import json
from io import StringIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from plataforma.models import GuardiaoLinkPendente, Project, ProjectLink


@override_settings(GUARDIAO_API_URL="https://guardiao.example/v1/guardiao/links",
                   GUARDIAO_SERVICE_TOKEN="token-teste")
class RejeicoesGuardiaoTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="rejeicoes-guardiao")
        self.project = Project.objects.create(owner=owner, title="Fila", direction="Contexto")
        self.bad = ProjectLink.objects.create(project=self.project, label="Rejeitado", url="https://example.com/a")
        self.good = ProjectLink.objects.create(project=self.project, label="Válido", url="https://example.com/b")

    @patch("plataforma.guardiao_ameacas.verificar_links_salvos")
    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_rejeicao_individual_preserva_item_e_processa_o_seguinte(self, build, threats):
        for code in (400, 422):
            with self.subTest(code=code):
                GuardiaoLinkPendente.objects.update_or_create(link_id=self.good.pk)
                sent = []

                def send(request, timeout):
                    item = json.loads(request.data)["links"][0]
                    sent.append(item["link_id"])
                    if item["link_id"] == self.bad.pk:
                        raise HTTPError("https://segredo.example/token", code, "detalhe privado", {}, None)
                    response = MagicMock()
                    response.__enter__.return_value.status = 202
                    return response

                build.return_value.open.side_effect = send
                stderr = StringIO()
                call_command("enviar_links_guardiao", stdout=StringIO(), stderr=stderr)
                self.assertEqual(sent.count(self.bad.pk), 1)
                self.assertIn(self.good.pk, sent)
                self.assertTrue(GuardiaoLinkPendente.objects.filter(pk=self.bad.pk).exists())
                self.assertFalse(GuardiaoLinkPendente.objects.filter(pk=self.good.pk).exists())
                self.assertIn(f"HTTP {code}", stderr.getvalue())
                self.assertNotIn("segredo", stderr.getvalue())
                self.assertNotIn("detalhe privado", stderr.getvalue())
        self.assertEqual(threats.call_count, 2)

    @patch("plataforma.guardiao_ameacas.verificar_links_salvos")
    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_falha_de_autorizacao_ou_servidor_preserva_a_fila(self, build, threats):
        for code in (401, 403, 429, 503):
            with self.subTest(code=code):
                build.return_value.open.side_effect = HTTPError("https://guardiao.example", code, "erro", {}, None)
                with self.assertRaises(CommandError):
                    call_command("enviar_links_guardiao", stdout=StringIO(), stderr=StringIO())
                self.assertTrue(GuardiaoLinkPendente.objects.filter(pk=self.bad.pk).exists())
                self.assertTrue(GuardiaoLinkPendente.objects.filter(pk=self.good.pk).exists())
        threats.assert_not_called()

    @patch("plataforma.guardiao_ameacas.verificar_links_salvos")
    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_corrigir_url_permite_sincronizar_item_preservado(self, build, threats):
        self.bad.url = "https://example.org/corrigido"
        self.bad.save()
        build.return_value.open.return_value.__enter__.return_value.status = 202
        call_command("enviar_links_guardiao", stdout=StringIO(), stderr=StringIO())
        self.assertFalse(GuardiaoLinkPendente.objects.exists())
        threats.assert_called_once_with()
