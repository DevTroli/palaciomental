import json
import threading
from io import StringIO
from unittest.mock import patch
from unittest import skipUnless
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from plataforma.models import GuardiaoLinkPendente, Project, ProjectLink


@override_settings(GUARDIAO_API_URL="https://guardiao.example/internal/guardiao/links",
                   GUARDIAO_SERVICE_TOKEN="segredo-teste")
class EnvioGuardiaoTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="autor-guardiao")
        self.project = Project.objects.create(owner=owner, title="Projeto", direction="Direção")
        self.link = ProjectLink.objects.create(project=self.project, label="Link", url="https://example.com/a")

    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_envia_estado_atual_e_remove_fila(self, build_opener):
        self.link.url = "https://example.com/b"
        self.link.save()
        response = build_opener.return_value.open.return_value.__enter__.return_value
        response.status = 202
        call_command("enviar_links_guardiao", stdout=StringIO())
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(json.loads(request.data), {"links": [{"link_id": self.link.pk, "url": self.link.url}]})
        self.assertEqual(request.get_header("Authorization"), "Bearer segredo-teste")
        self.assertFalse(GuardiaoLinkPendente.objects.exists())

    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_exclusao_envia_id_e_pode_ser_repetida(self, build_opener):
        link_id = self.link.pk
        self.link.delete()
        response = build_opener.return_value.open.return_value.__enter__.return_value
        response.status = 204
        call_command("enviar_links_guardiao", stdout=StringIO())
        request = build_opener.return_value.open.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/links/delete"))
        self.assertEqual(json.loads(request.data), {"link_id": link_id})
        self.assertFalse(GuardiaoLinkPendente.objects.exists())

    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_falha_preserva_fila(self, build_opener):
        build_opener.return_value.open.side_effect = URLError("indisponível")
        with self.assertRaises(CommandError):
            call_command("enviar_links_guardiao", stdout=StringIO())
        self.assertTrue(GuardiaoLinkPendente.objects.filter(pk=self.link.pk).exists())

    def test_rollback_descarta_alteracao_e_fila(self):
        GuardiaoLinkPendente.objects.all().delete()
        with self.assertRaises(ValueError), transaction.atomic():
            self.link.url = "https://example.com/c"
            self.link.save()
            raise ValueError()
        self.link.refresh_from_db()
        self.assertEqual(self.link.url, "https://example.com/a")
        self.assertFalse(GuardiaoLinkPendente.objects.exists())

    def test_exclusao_do_projeto_enfileira_links(self):
        link_id = self.link.pk
        GuardiaoLinkPendente.objects.all().delete()
        self.project.delete()
        self.assertTrue(GuardiaoLinkPendente.objects.filter(pk=link_id).exists())

    @override_settings(GUARDIAO_API_URL="http://guardiao.example/internal/guardiao/links")
    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_nao_envia_token_sem_https(self, build_opener):
        with self.assertRaises(CommandError):
            call_command("enviar_links_guardiao")
        build_opener.assert_not_called()

    @override_settings(GUARDIAO_API_URL="", STATUS_API_URL="", GUARDIAO_SERVICE_TOKEN="")
    def test_informa_url_ausente_antes_de_entrar_no_modo_continuo(self):
        with self.assertRaisesMessage(CommandError, "Defina STATUS_API_URL"):
            call_command("enviar_links_guardiao", continuo=True)

    @override_settings(GUARDIAO_API_URL="https://guardiao.example/", GUARDIAO_SERVICE_TOKEN="")
    def test_informa_token_ausente(self):
        with self.assertRaisesMessage(CommandError, "Defina GUARDIAO_SERVICE_TOKEN"):
            call_command("enviar_links_guardiao")

    @override_settings(GUARDIAO_API_URL="https://guardiao.example/")
    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_aceita_url_base_da_api(self, build_opener):
        build_opener.return_value.open.return_value.__enter__.return_value.status = 202
        call_command("enviar_links_guardiao", stdout=StringIO())
        self.assertEqual(build_opener.return_value.open.call_args.args[0].full_url,
                         "https://guardiao.example/internal/guardiao/links")

    @override_settings(GUARDIAO_API_URL="", STATUS_API_URL="https://status.example:8443/v1/status")
    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_aproveita_url_de_status(self, build_opener):
        build_opener.return_value.open.return_value.__enter__.return_value.status = 202
        call_command("enviar_links_guardiao", stdout=StringIO())
        self.assertEqual(build_opener.return_value.open.call_args.args[0].full_url,
                         "https://status.example:8443/internal/guardiao/links")

    @override_settings(GUARDIAO_API_URL="", STATUS_API_URL="http://status.example/v1/status")
    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_url_de_status_http_nao_recebe_token(self, build_opener):
        with self.assertRaises(CommandError):
            call_command("enviar_links_guardiao")
        build_opener.assert_not_called()

    @override_settings(DEBUG=True, GUARDIAO_LOCAL_HTTP=True, GUARDIAO_API_URL="",
                       STATUS_API_URL="http://status-api:8080/v1/status")
    @patch("plataforma.management.commands.enviar_links_guardiao.build_opener")
    def test_http_local_explicito_permite_worker(self, build_opener):
        build_opener.return_value.open.return_value.__enter__.return_value.status = 202
        call_command("enviar_links_guardiao", stdout=StringIO())
        self.assertEqual(build_opener.return_value.open.call_args.args[0].full_url,
                         "http://status-api:8080/internal/guardiao/links")

    @override_settings(DEBUG=False, GUARDIAO_LOCAL_HTTP=True, GUARDIAO_API_URL="",
                       STATUS_API_URL="http://status-api:8080/v1/status")
    def test_http_local_nao_funciona_sem_debug(self):
        with self.assertRaises(CommandError):
            call_command("enviar_links_guardiao")

    @override_settings(DEBUG=True, GUARDIAO_LOCAL_HTTP=True, GUARDIAO_API_URL="",
                       STATUS_API_URL="http://outro-host:8080/v1/status")
    def test_http_local_nao_permite_outro_host(self):
        with self.assertRaises(CommandError):
            call_command("enviar_links_guardiao")


@skipUnless(connection.vendor == "postgresql", "Requer locks do PostgreSQL")
@override_settings(GUARDIAO_API_URL="https://guardiao.example/internal/guardiao/links",
                   GUARDIAO_SERVICE_TOKEN="segredo-teste")
class ConcorrenciaGuardiaoTests(TransactionTestCase):
    def test_edicao_durante_envio_permanece_na_fila(self):
        owner = get_user_model().objects.create_user(username="concorrencia")
        project = Project.objects.create(owner=owner, title="Projeto", direction="Direção")
        link = ProjectLink.objects.create(project=project, label="Link", url="https://example.com/a")
        started, release, edited = threading.Event(), threading.Event(), threading.Event()
        errors = []

        class Response:
            status = 202
            def __enter__(self):
                started.set()
                if not release.wait(5):
                    raise TimeoutError("Envio não liberado")
                return self
            def __exit__(self, *args):
                return False

        def worker():
            try:
                call_command("enviar_links_guardiao", stdout=StringIO())
            except Exception as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        def edit():
            try:
                item = ProjectLink.objects.get(pk=link.pk)
                item.url = "https://example.com/b"
                item.save()
                edited.set()
            except Exception as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        with patch("plataforma.management.commands.enviar_links_guardiao.build_opener") as opener:
            opener.return_value.open.return_value = Response()
            sender = threading.Thread(target=worker)
            sender.start()
            self.assertTrue(started.wait(5))
            editor = threading.Thread(target=edit)
            editor.start()
            self.assertFalse(edited.wait(0.2))
            release.set()
            sender.join(5)
            editor.join(5)
        self.assertFalse(sender.is_alive())
        self.assertFalse(editor.is_alive())
        self.assertFalse(errors)
        self.assertTrue(edited.is_set())
        pending = GuardiaoLinkPendente.objects.filter(pk=link.pk).exists()
        sent = [json.loads(call.args[0].data)["links"][0]["url"] for call in opener.return_value.open.call_args_list]
        self.assertTrue(pending or "https://example.com/b" in sent)
