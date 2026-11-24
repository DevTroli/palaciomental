from io import StringIO
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from plataforma.legacy_transition import LEGACY_LABEL, transition


@skipUnless(connection.vendor == "postgresql", "Transição exige PostgreSQL")
class AppTransitionTests(TestCase):
    def setUp(self):
        self.content_type = ContentType.objects.get(app_label="plataforma", model="project")
        self.permissions = list(Permission.objects.filter(content_type=self.content_type).values_list("id", flat=True))
        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE plataforma_project RENAME TO "listaEspera_project"')
            cursor.execute("UPDATE django_migrations SET app=%s WHERE app='plataforma'", [LEGACY_LABEL])
            cursor.execute("UPDATE django_content_type SET app_label=%s WHERE app_label='plataforma'", [LEGACY_LABEL])

    def test_transition_preserves_identity_permissions_and_rls(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT oid, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname=%s', [LEGACY_LABEL + '_project'])
            before = cursor.fetchone()
        self.assertGreater(transition(connection, apply=False), 0)
        with self.assertRaises(CommandError):
            call_command("migrate", stdout=StringIO())
        transition(connection, apply=True)
        self.content_type.refresh_from_db()
        self.assertEqual(self.content_type.app_label, "plataforma")
        self.assertEqual(list(Permission.objects.filter(content_type=self.content_type).values_list("id", flat=True)), self.permissions)
        with connection.cursor() as cursor:
            cursor.execute("SELECT oid, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='plataforma_project'")
            self.assertEqual(cursor.fetchone(), before)
        self.assertEqual(transition(connection, apply=True), 0)
        self.assertIn('/plataforma/project/', reverse('admin:plataforma_project_changelist'))

    def test_conflicting_destination_is_rejected_without_changes(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE plataforma_project (id integer)')
        with self.assertRaises(CommandError):
            transition(connection, apply=True)
        self.content_type.refresh_from_db()
        self.assertEqual(self.content_type.app_label, LEGACY_LABEL)

    def test_error_rolls_back_renames(self):
        original = connection.ops.quote_name

        def fail_on_target(name):
            if name == "plataforma_project":
                raise RuntimeError("Falha simulada durante a transição")
            return original(name)

        with patch.object(connection.ops, "quote_name", side_effect=fail_on_target):
            with self.assertRaises(RuntimeError):
                transition(connection, apply=True)
        self.assertIn(LEGACY_LABEL + '_project', connection.introspection.table_names())
        self.content_type.refresh_from_db()
        self.assertEqual(self.content_type.app_label, LEGACY_LABEL)
