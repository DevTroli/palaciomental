from django.test import TestCase
from django.utils import timezone

from plataforma.models import GuardiaoLinkPendente


class QuarentenaModeloTests(TestCase):
    def test_nova_entrada_nao_comeca_em_quarentena(self):
        entry = GuardiaoLinkPendente.objects.create(link_id=900001)
        entry.refresh_from_db()
        self.assertFalse(entry.quarentena)
        self.assertIsNone(entry.rejeicao_http)
        self.assertIsNone(entry.rejeitada_em)

    def test_quarentena_persiste_em_nova_leitura_sem_apagar_entrada(self):
        now = timezone.now()
        GuardiaoLinkPendente.objects.create(
            link_id=900002, quarentena=True, rejeicao_http=400, rejeitada_em=now,
        )
        entry = GuardiaoLinkPendente.objects.get(link_id=900002)
        self.assertTrue(entry.quarentena)
        self.assertEqual(entry.rejeicao_http, 400)
        self.assertEqual(entry.rejeitada_em, now)
        self.assertEqual(GuardiaoLinkPendente.objects.filter(link_id=900002).count(), 1)
