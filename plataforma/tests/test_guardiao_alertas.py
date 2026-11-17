import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Barrier
from types import SimpleNamespace
from urllib.error import URLError
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from plataforma.experience import _notificacoes_tenant
from plataforma.guardiao_alertas import sincronizar_alertas
from plataforma.models import DominioOrganizacao, MembroOrganizacao, Notification, Organizacao


class Response(BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Opener:
    def __init__(self, events, fail_ack=False):
        self.events, self.fail_ack, self.calls = events, fail_ack, []

    def open(self, request, timeout):
        self.calls.append((request.get_method(), request.full_url))
        if request.get_method() == "GET":
            return Response(json.dumps(self.events).encode())
        if self.fail_ack:
            raise URLError("indisponível")
        result = Response(b"")
        result.status = 204
        return result


class AlertasGuardiaoTests(TestCase):
    endpoint = "https://guardiao.example/v1/guardiao/links"

    def setUp(self):
        user = get_user_model()
        self.aluno = user.objects.create_user(username="alerta-aluno")
        self.outro = user.objects.create_user(username="alerta-outro")
        self.suspenso = user.objects.create_user(username="alerta-suspenso")
        self.inativo = user.objects.create_user(username="alerta-inativo", is_active=False)
        self.org = Organizacao.objects.create(slug="alerta-a", nome="A", status=Organizacao.STATUS_ATIVA)
        self.outra_org = Organizacao.objects.create(slug="alerta-b", nome="B", status=Organizacao.STATUS_ATIVA)
        DominioOrganizacao.objects.create(organizacao=self.org, hostname="a.example", principal=True, status_verificacao="ativo")
        MembroOrganizacao.objects.create(organizacao=self.org, usuario=self.aluno, status=MembroOrganizacao.STATUS_ATIVA)
        MembroOrganizacao.objects.create(organizacao=self.org, usuario=self.suspenso, status=MembroOrganizacao.STATUS_SUSPENSA)
        MembroOrganizacao.objects.create(organizacao=self.org, usuario=self.inativo, status=MembroOrganizacao.STATUS_ATIVA)
        MembroOrganizacao.objects.create(organizacao=self.outra_org, usuario=self.outro, status=MembroOrganizacao.STATUS_ATIVA)

    def evento(self, event_id=10, journey="organizacao", created=None, recovered=None):
        created = created or timezone.now()
        return {"id": event_id, "journey": journey, "tenantHost": "a.example" if journey == "organizacao" else None,
                "startedAt": (created - timedelta(hours=2)).isoformat(),
                "createdAt": created.isoformat(),
                "recoveredAt": recovered.isoformat() if recovered else None}

    def test_tenant_atinge_somente_membros_ativos_e_nao_duplica(self):
        opener = Opener([self.evento()])
        sincronizar_alertas(self.endpoint, "token", opener)
        sincronizar_alertas(self.endpoint, "token", opener)
        self.assertEqual(list(Notification.objects.values_list("recipient_id", flat=True)), [self.aluno.pk])
        self.assertEqual(Notification.objects.get().scope_organization, self.org)
        self.assertEqual(sum(method == "POST" for method, _ in opener.calls), 2)
        request = SimpleNamespace(user=self.aluno, organizacao=self.org)
        self.assertEqual(_notificacoes_tenant(request).count(), 1)
        request.organizacao = self.outra_org
        self.assertEqual(_notificacoes_tenant(request).count(), 0)

    def test_global_atinge_contas_ativas_e_usuario_inativo_nao_recebe(self):
        sincronizar_alertas(self.endpoint, "token", Opener([self.evento(journey="vitrine")]))
        self.assertSetEqual(set(Notification.objects.values_list("recipient_id", flat=True)),
                            {self.aluno.pk, self.outro.pk, self.suspenso.pk})
        self.assertEqual(_notificacoes_tenant(SimpleNamespace(user=self.aluno, organizacao=self.org)).count(), 1)

    def test_retentativa_apos_falha_na_confirmacao_nao_duplica(self):
        event = self.evento()
        with self.assertRaises(ValueError):
            sincronizar_alertas(self.endpoint, "token", Opener([event], fail_ack=True))
        sincronizar_alertas(self.endpoint, "token", Opener([event]))
        self.assertEqual(Notification.objects.count(), 1)

    @patch("plataforma.guardiao_alertas._criar_notificacoes", side_effect=DatabaseError("detalhe privado"))
    def test_falha_de_gravacao_e_registrada_sem_confirmar(self, _criar):
        opener = Opener([self.evento()])
        with self.assertLogs("plataforma.guardiao_alertas", level="WARNING") as logs:
            with self.assertRaises(ValueError):
                sincronizar_alertas(self.endpoint, "token", opener)
        self.assertTrue(any(url.endswith("/10/falha") for _, url in opener.calls))
        self.assertFalse(any(url.endswith("/10/confirmar") for _, url in opener.calls))
        self.assertFalse(Notification.objects.exists())
        self.assertNotIn("detalhe privado", " ".join(logs.output))

    def test_antigo_e_descartado_e_tenant_desconhecido_e_rejeitado(self):
        old = self.evento(created=timezone.now() - timedelta(hours=25))
        unknown = self.evento(event_id=11)
        unknown["tenantHost"] = "desconhecido.example"
        opener = Opener([old, unknown])
        sincronizar_alertas(self.endpoint, "token", opener)
        self.assertFalse(Notification.objects.exists())
        self.assertTrue(any(url.endswith("/11/rejeitar") for _, url in opener.calls))
        self.assertFalse(any(url.endswith("/10/confirmar") for _, url in opener.calls))

    def test_apos_recuperacao_aviso_informa_que_falha_ja_terminou(self):
        event = self.evento(recovered=timezone.now())
        sincronizar_alertas(self.endpoint, "token", Opener([event]))
        self.assertIn("já foi recuperado", Notification.objects.get().message)

    def test_caixa_global_oculta_aviso_institucional_apos_suspensao(self):
        sincronizar_alertas(self.endpoint, "token", Opener([self.evento()]))
        self.client.force_login(self.aluno)
        self.assertContains(self.client.get(reverse("plataforma:inbox")), "falha prolongada")
        MembroOrganizacao.objects.filter(organizacao=self.org, usuario=self.aluno).update(status=MembroOrganizacao.STATUS_SUSPENSA)
        self.assertNotContains(self.client.get(reverse("plataforma:inbox")), "falha prolongada")


@skipUnless(connection.vendor == "postgresql", "Concorrência validada com PostgreSQL")
class AlertasConcorrentesTests(TransactionTestCase):
    def test_dois_workers_nao_criam_aviso_duplicado(self):
        get_user_model().objects.create_user(username="alerta-concorrente")
        now = timezone.now()
        event = {"id": 99, "journey": "entrada", "tenantHost": None,
                 "startedAt": (now - timedelta(hours=2)).isoformat(), "createdAt": now.isoformat(), "recoveredAt": None}
        barrier = Barrier(2)

        def run_worker():
            try:
                barrier.wait(timeout=10)
                sincronizar_alertas("https://guardiao.example/v1/guardiao/links", "token", Opener([event]))
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run_worker) for _ in range(2)]
            for future in futures:
                future.result(timeout=20)
        self.assertEqual(Notification.objects.filter(source_key="status-incident:99").count(), 1)
