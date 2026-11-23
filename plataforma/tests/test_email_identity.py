from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from io import StringIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.db import close_old_connections, connection, connections, IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from plataforma.account_identity import register_account
from plataforma.experience_forms import PerfilInstitucionalForm
from plataforma.forms import MemberCreationForm
from plataforma.models import MemberProfile

User = get_user_model()
PASSWORD = "Teste-identidade-2026-seguro"


def registration(username, email):
    return MemberCreationForm({"username": username, "first_name": "Pessoa",
                               "email": email, "password1": PASSWORD, "password2": PASSWORD})


class EmailIdentityTests(TestCase):
    def test_database_rejects_case_and_surrounding_spaces(self):
        User.objects.create_user(username="one", email="person@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username="two", email=" PERSON@EXAMPLE.COM ")

    def test_blank_email_allowed_for_technical_accounts(self):
        User.objects.create_user(username="one", email="")
        User.objects.create_user(username="two", email=" ")
        self.assertEqual(User.objects.count(), 2)

    def test_forms_detect_legacy_surrounding_spaces(self):
        User.objects.create_user(username="one", email=" PERSON@EXAMPLE.COM ")
        form = registration("two", "person@example.com")
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        user = User.objects.create_user(username="three", email="other@example.com")
        profile = PerfilInstitucionalForm({"first_name": "Pessoa", "email": "person@example.com"}, instance=user)
        self.assertFalse(profile.is_valid())
        self.assertIn("email", profile.errors)

    def test_registration_race_becomes_field_error_without_partial_profile(self):
        form = registration("new", "person@example.com")
        self.assertTrue(form.is_valid(), form.errors)
        User.objects.create_user(username="other", email="PERSON@example.com")
        self.assertIsNone(register_account(form))
        self.assertIn("email", form.errors)
        self.assertFalse(User.objects.filter(username="new").exists())
        self.assertFalse(MemberProfile.objects.filter(user__username="new").exists())

    def test_inventory_does_not_print_email(self):
        User.objects.create_user(username="one", email="person@example.com")
        output = StringIO()
        call_command("verificar_emails", stdout=output)
        self.assertNotIn("person@example.com", output.getvalue())


@skipUnless(connection.vendor == "postgresql", "Concorrência e migração exigem PostgreSQL")
class EmailIdentityPostgresTests(TransactionTestCase):
    def test_concurrent_registration_allows_one_account(self):
        barrier = Barrier(2)

        def create(number):
            close_old_connections()
            try:
                form = registration(f"person{number}", ["Person@example.com", "person@EXAMPLE.com"][number])
                self.assertTrue(form.is_valid(), form.errors)
                barrier.wait(timeout=10)
                user = register_account(form)
                return user is not None, bool(form.errors.get("email"))
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create, range(2)))
        self.assertCountEqual(results, [(True, False), (False, True)])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(MemberProfile.objects.count(), 1)

    def test_migration_refuses_duplicates_without_changing_accounts_and_is_reversible(self):
        migration = import_module("plataforma.migrations.0042_unique_user_email")
        with connection.schema_editor() as editor:
            migration.remove_unique_email(apps, editor)
        try:
            one = User.objects.create_user(username="one", email="Person@example.com")
            two = User.objects.create_user(username="two", email="person@example.com")
            with self.assertRaisesRegex(RuntimeError, "1 grupos"):
                with connection.schema_editor() as editor:
                    migration.enforce_unique_email(apps, editor)
            self.assertEqual(User.objects.filter(pk__in=[one.pk, two.pk]).count(), 2)
            output = StringIO()
            with self.assertRaises(CommandError):
                call_command("verificar_emails", stdout=output)
            self.assertIn(str(one.pk), output.getvalue())
            self.assertNotIn("example.com", output.getvalue())
            # Resolução somente nas contas descartáveis deste teste.
            two.delete()
        finally:
            with connection.schema_editor() as editor:
                migration.enforce_unique_email(apps, editor)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username="three", email="PERSON@example.com")


from .institucional.base import PortalInstitucionalBase
from plataforma.models import MembroOrganizacao


class EmailRaceHttpTests(PortalInstitucionalBase):
    def test_signup_race_has_readable_error(self):
        payload = {"username": "new-person", "first_name": "Pessoa", "email": self.user.email,
                   "password1": PASSWORD, "password2": PASSWORD}
        with patch("plataforma.forms.email_users") as users:
            users.return_value.exists.return_value = False
            response = self.client.post("/cadastrar/", payload, HTTP_HOST="palaciomental.com.br")
        self.assertContains(response, "Este e-mail já está cadastrado.")
        self.assertFalse(User.objects.filter(username="new-person").exists())

    def test_profile_race_has_field_error_and_preserves_email(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user)
        self.client.force_login(self.user)
        with patch("plataforma.experience_forms.email_users") as users:
            users.return_value.exclude.return_value.exists.return_value = False
            response = self.client.post("/perfil/", {
                "form": "perfil", "first_name": "Pessoa", "email": self.pm_staff.email,
            }, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(response, "Este e-mail já está cadastrado.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "participante@example.com")
