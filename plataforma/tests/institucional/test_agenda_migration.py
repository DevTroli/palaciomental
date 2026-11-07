from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class AgendaMigrationTests(TransactionTestCase):
    before = [("listaEspera", "0029_merge_memberprofile_comment_indexes")]
    created = [("listaEspera", "0030_criar_agenda")]

    def test_creation_starts_empty_and_preserves_existing_platform_data(self):
        executor = MigrationExecutor(connection)
        final = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(self.before)
            apps = executor.loader.project_state(self.before).apps
            user = apps.get_model("auth", "User").objects.create(username="migration-user")
            org = apps.get_model("listaEspera", "Organizacao").objects.create(nome="Agenda", slug="migration", status="ativa")
            executor = MigrationExecutor(connection)
            executor.migrate(final)
            apps = executor.loader.project_state(final).apps
            event_model = apps.get_model("listaEspera", "EventoCalendario")
            self.assertEqual(event_model._meta.db_table, "plataforma_eventocalendario")
            self.assertFalse(event_model.objects.exists())
            self.assertTrue(apps.get_model("auth", "User").objects.filter(pk=user.pk).exists())
            self.assertTrue(apps.get_model("listaEspera", "Organizacao").objects.filter(pk=org.pk).exists())
            parents = executor.loader.graph.node_map[("listaEspera", "0030_criar_agenda")].parents
            self.assertTrue({parent.key[0] for parent in parents}.issubset({"listaEspera", "auth"}))
        finally:
            MigrationExecutor(connection).migrate(final)

    def test_rls_migration_keeps_events_created_by_new_agenda(self):
        executor = MigrationExecutor(connection)
        final = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(self.created)
            apps = executor.loader.project_state(self.created).apps
            user = apps.get_model("auth", "User").objects.create(username="agenda-policy")
            org = apps.get_model("listaEspera", "Organizacao").objects.create(nome="Agenda", slug="policy", status="ativa")
            event = apps.get_model("listaEspera", "EventoCalendario").objects.create(
                aluno_id=user.pk, organizacao_id=org.pk, titulo="Nova entrega",
                data=date(2026, 11, 7), origem="aluno", tipo="trabalho", status="entregue",
            )
            executor = MigrationExecutor(connection)
            executor.migrate(final)
            model = executor.loader.project_state(final).apps.get_model("listaEspera", "EventoCalendario")
            saved = model.objects.get(pk=event.pk)
            self.assertEqual((saved.organizacao_id, saved.aluno_id, saved.status), (org.pk, user.pk, "entregue"))
        finally:
            MigrationExecutor(connection).migrate(final)
