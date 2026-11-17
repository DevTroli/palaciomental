import json
from io import StringIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from plataforma.models import GuardiaoLinkPendente, Project, ProjectLink


@override_settings(GUARDIAO_API_URL="https://guardiao.example/v1/guardiao/links",
                   GUARDIAO_SERVICE_TOKEN="token-teste")
class RejeicoesGuardiaoTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="rejeicoes-guardiao")
        self.project = Project.objects.create(owner=owner, title="Fila", direction="Contexto")
        self.bad = ProjectLink.objects.create(project=self.project, label="Rejeitado", url="https://example.com/a")
        self.good = ProjectLink.objects.create(project=self.project, label="Válido", url="https://example.com/b")
        network = patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
        self.build = network.start()
        self.addCleanup(network.stop)
        checker = patch("plataforma.guardiao_ameacas.verificar_links_salvos")
        self.threats = checker.start()
        self.addCleanup(checker.stop)
        self.build.return_value.open.return_value.__enter__.return_value.status = 202

    def sync(self):
        call_command("enviar_links_guardiao", stdout=StringIO(), stderr=StringIO())

    def quarantine(self):
        GuardiaoLinkPendente.objects.filter(pk=self.bad.pk).update(
            quarentena=True, rejeicao_http=400, rejeitada_em=timezone.now(),
        )

    def test_rejeicao_individual_preserva_item_e_processa_o_seguinte(self):
        for code in (400, 422):
            with self.subTest(code=code):
                GuardiaoLinkPendente.objects.filter(pk=self.bad.pk).update(
                    quarentena=False, rejeicao_http=None, rejeitada_em=None,
                )
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

                self.build.return_value.open.side_effect = send
                stderr = StringIO()
                call_command("enviar_links_guardiao", stdout=StringIO(), stderr=stderr)
                self.assertEqual(sent.count(self.bad.pk), 1)
                self.assertIn(self.good.pk, sent)
                entry = GuardiaoLinkPendente.objects.get(pk=self.bad.pk)
                self.assertTrue(entry.quarentena)
                self.assertEqual(entry.rejeicao_http, code)
                self.assertIsNotNone(entry.rejeitada_em)
                self.assertFalse(GuardiaoLinkPendente.objects.filter(pk=self.good.pk).exists())
                self.assertIn(f"HTTP {code}", stderr.getvalue())
                self.assertNotIn("segredo", stderr.getvalue())
                self.assertNotIn("detalhe privado", stderr.getvalue())
                before = len(sent)
                self.sync()
                self.assertEqual(len(sent), before)
        self.assertEqual(self.threats.call_count, 4)

    def test_falha_de_autorizacao_ou_servidor_preserva_a_fila(self):
        for code in (401, 403, 429, 503):
            with self.subTest(code=code):
                self.build.return_value.open.side_effect = HTTPError("https://guardiao.example", code, "erro", {}, None)
                with self.assertRaises(CommandError):
                    self.sync()
                self.assertEqual(GuardiaoLinkPendente.objects.count(), 2)
                self.assertFalse(GuardiaoLinkPendente.objects.filter(quarentena=True).exists())
        self.threats.assert_not_called()

    def test_corrigir_url_reativa_e_limpa_rejeicao(self):
        self.quarantine()
        self.bad.url = "https://example.org/corrigido"
        self.bad.save()
        entry = GuardiaoLinkPendente.objects.get(pk=self.bad.pk)
        self.assertFalse(entry.quarentena)
        self.assertIsNone(entry.rejeicao_http)
        self.assertIsNone(entry.rejeitada_em)
        self.sync()
        self.assertFalse(GuardiaoLinkPendente.objects.exists())

    def test_editar_titulo_nao_reativa_url_rejeitada(self):
        self.quarantine()
        self.bad.label = "Novo título"
        self.bad.save(update_fields=["label"])
        self.assertTrue(GuardiaoLinkPendente.objects.get(pk=self.bad.pk).quarentena)

    def test_url_nao_persistida_por_update_fields_nao_reativa(self):
        self.quarantine()
        self.bad.url = "https://example.org/nao-salvo"
        self.bad.label = "Novo título"
        self.bad.save(update_fields=["label"])
        self.assertTrue(GuardiaoLinkPendente.objects.get(pk=self.bad.pk).quarentena)
        self.bad.refresh_from_db()
        self.assertEqual(self.bad.url, "https://example.com/a")

    def test_excluir_link_reativa_operacao_delete(self):
        self.quarantine()
        link_id = self.bad.pk
        self.bad.delete()
        entry = GuardiaoLinkPendente.objects.get(pk=link_id)
        self.assertFalse(entry.quarentena)
        self.assertIsNone(entry.rejeicao_http)
        self.build.return_value.open.return_value.__enter__.return_value.status = 204
        GuardiaoLinkPendente.objects.filter(pk=self.good.pk).delete()
        self.sync()
        request = self.build.return_value.open.call_args.args[0]
        self.assertEqual(request.get_method(), "DELETE")
        self.assertTrue(request.full_url.endswith(f"/links/{link_id}"))
        self.assertFalse(GuardiaoLinkPendente.objects.filter(pk=link_id).exists())

    def test_rollback_da_correcao_preserva_quarentena(self):
        self.quarantine()
        with self.assertRaises(ValueError), transaction.atomic():
            self.bad.url = "https://example.org/rollback"
            self.bad.save()
            raise ValueError("Reverter")
        self.assertTrue(GuardiaoLinkPendente.objects.get(pk=self.bad.pk).quarentena)
        self.bad.refresh_from_db()
        self.assertEqual(self.bad.url, "https://example.com/a")

    def test_reprocessamento_explicito_libera_somente_id_solicitado(self):
        self.quarantine()
        GuardiaoLinkPendente.objects.filter(pk=self.good.pk).update(quarentena=True)
        call_command("reprocessar_link_guardiao", self.bad.pk, stdout=StringIO())
        entry = GuardiaoLinkPendente.objects.get(pk=self.bad.pk)
        self.assertFalse(entry.quarentena)
        self.assertIsNone(entry.rejeicao_http)
        self.assertIsNone(entry.rejeitada_em)
        self.assertTrue(GuardiaoLinkPendente.objects.get(pk=self.good.pk).quarentena)
        self.build.return_value.open.assert_not_called()

    def test_reprocessamento_rejeita_id_invalido_ou_ausente(self):
        for link_id in (0, -1, 999999):
            with self.subTest(link_id=link_id), self.assertRaises(CommandError):
                call_command("reprocessar_link_guardiao", link_id, stdout=StringIO())
