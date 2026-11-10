from datetime import date
from unittest import skipUnless

from django.db import connection, transaction, DatabaseError
from django.test import TestCase

from django.contrib.auth import get_user_model
from plataforma import rls
from plataforma.models import EventoCalendario, Organizacao


@skipUnless(connection.vendor == "postgresql", "RLS exige PostgreSQL")
class AgendaRLSTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="agenda-rls")
        self.a = Organizacao.objects.create(nome="A", slug="agenda-a", status="ativa")
        self.b = Organizacao.objects.create(nome="B", slug="agenda-b", status="ativa")
        self.event_a = EventoCalendario.objects.create(organizacao=self.a, aluno=self.user, titulo="A", data=date.today())
        self.event_b = EventoCalendario.objects.create(organizacao=self.b, aluno=self.user, titulo="B", data=date.today())

    def test_unscoped_query_is_still_isolated_by_database(self):
        with rls.rls_context(rls.MODE_TENANT, self.a.pk):
            self.assertEqual(list(EventoCalendario.objects.values_list("pk", flat=True)), [self.event_a.pk])
            self.assertEqual(EventoCalendario.objects.filter(pk=self.event_b.pk).update(titulo="Inválido"), 0)
        with rls.rls_context(rls.MODE_GLOBAL):
            self.assertFalse(EventoCalendario.objects.exists())

    def test_forged_tenant_insert_is_rejected_by_database(self):
        with rls.rls_context(rls.MODE_TENANT, self.a.pk):
            with self.assertRaises(DatabaseError), transaction.atomic():
                EventoCalendario.objects.create(organizacao=self.b, aluno=self.user, titulo="Forjado", data=date.today())
