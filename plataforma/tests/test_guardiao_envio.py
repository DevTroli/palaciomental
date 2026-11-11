import json
from io import StringIO
from unittest.mock import patch
from urllib.error import URLError

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


@override_settings(GUARDIAO_API_URL="https://guardiao.example/internal/guardiao/links",
                   GUARDIAO_SERVICE_TOKEN="segredo-teste")
class EnvioGuardiaoTests(SimpleTestCase):
    @patch("plataforma.management.commands.enviar_links_guardiao.system_context")
    @patch("plataforma.management.commands.enviar_links_guardiao.ProjectLink")
    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_envia_apenas_id_e_url_em_lotes(self, build_opener, model, context):
        context.return_value.__enter__.return_value = None
        rows = [(i, f"https://example.com/{i}") for i in range(1, 101)]
        query = model.objects.filter.return_value.order_by.return_value.values_list.return_value
        query.__getitem__.side_effect = [rows, [(101, "https://example.com/101")], []]
        opener = build_opener.return_value
        responses = []
        for status in (201, 202, 202, 204):
            response_obj = type("Response", (), {
                "status": status,
                "read": lambda self, n: b'{"id":"29b676ee-2137-48b0-b455-a140cf0641dd"}',
                "__enter__": lambda self: self,
                "__exit__": lambda self, *args: None,
            })()
            responses.append(response_obj)
        opener.open.side_effect = responses
        output = StringIO()
        call_command("enviar_links_guardiao", stdout=output)
        self.assertEqual(opener.open.call_count, 4)
        first = opener.open.call_args_list[1].args[0]
        payload = json.loads(first.data)
        self.assertEqual(len(payload["links"]), 100)
        self.assertEqual(set(payload["links"][0]), {"link_id", "url"})
        self.assertEqual(first.get_header("Authorization"), "Bearer segredo-teste")
        self.assertIn("101 link(s)", output.getvalue())

    @override_settings(GUARDIAO_API_URL="http://guardiao.example/internal/guardiao/links")
    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_nao_envia_token_sem_https(self, build_opener):
        with self.assertRaises(CommandError):
            call_command("enviar_links_guardiao")
        build_opener.assert_not_called()

    @patch("plataforma.management.commands.enviar_links_guardiao.system_context")
    @patch("plataforma.management.commands.enviar_links_guardiao.ProjectLink")
    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_falha_no_lote_nao_conclui_sincronizacao(self, build_opener, model, context):
        context.return_value.__enter__.return_value = None
        query = model.objects.filter.return_value.order_by.return_value.values_list.return_value
        query.__getitem__.return_value = [(1, "https://example.com/")]
        opener = build_opener.return_value
        response = opener.open.return_value.__enter__.return_value
        response.status = 201
        response.read.return_value = b'{"id":"29b676ee-2137-48b0-b455-a140cf0641dd"}'
        opener.open.side_effect = [opener.open.return_value, URLError("indisponível")]
        with self.assertRaises(CommandError):
            call_command("enviar_links_guardiao")
        self.assertEqual(opener.open.call_count, 2)
