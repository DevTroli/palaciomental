from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections, close_old_connections, DatabaseError
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from plataforma.auth_limits import client_address, consume_attempt
from plataforma.models import AuthAttemptWindow
from .institucional.base import PortalInstitucionalBase


class AuthLimitTests(TestCase):
    def test_account_limit_expires_without_extension_from_blocked_requests(self):
        now = timezone.now()
        with patch("plataforma.auth_limits.timezone.now", return_value=now):
            for _ in range(10):
                self.assertEqual(consume_attempt("login", "Person", "192.0.2.1"), 0)
            self.assertEqual(consume_attempt("login", "person", "192.0.2.2"), 900)
        with patch("plataforma.auth_limits.timezone.now", return_value=now + timedelta(minutes=14)):
            self.assertEqual(consume_attempt("login", "person", "192.0.2.2"), 60)
        with patch("plataforma.auth_limits.timezone.now", return_value=now + timedelta(minutes=15)):
            self.assertEqual(consume_attempt("login", "person", "192.0.2.2"), 0)

    def test_origin_limit_applies_across_account_names(self):
        for number in range(60):
            self.assertEqual(consume_attempt("register", str(number), "192.0.2.1"), 0)
        previous_count = AuthAttemptWindow.objects.count()
        self.assertGreater(consume_attempt("register", "another", "192.0.2.1"), 0)
        self.assertEqual(AuthAttemptWindow.objects.count(), previous_count)
        self.assertEqual(consume_attempt("register", "another", "192.0.2.2"), 0)
        self.assertFalse(AuthAttemptWindow.objects.filter(key__contains="192.0.2").exists())

    def test_forwarded_address_requires_trusted_peer_and_chain(self):
        request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.1", HTTP_X_FORWARDED_FOR="198.51.100.4")
        self.assertEqual(client_address(request), "192.0.2.1")
        with override_settings(AUTH_TRUSTED_PROXY_NETWORKS=["192.0.2.0/24"]):
            self.assertEqual(client_address(request), "198.51.100.4")
            request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 198.51.100.4"
            self.assertEqual(client_address(request), "198.51.100.4")


class AuthLimitHttpTests(PortalInstitucionalBase):
    def test_login_block_is_generic_and_has_retry_header(self):
        for username in (self.user.username, "does-not-exist"):
            for _ in range(10):
                consume_attempt("login", username, "192.0.2.1")
            response = self.client.post("/entrar/", {"username": username, "password": "wrong"},
                                        HTTP_HOST="palaciomental.com.br", REMOTE_ADDR="192.0.2.2")
            self.assertContains(response, "Aguarde antes de tentar novamente", status_code=429)
            self.assertIn("Retry-After", response)
            self.assertEqual(response["Cache-Control"], "no-store")
            self.assertNotContains(response, username, status_code=429)

    def test_database_failure_is_visible_and_does_not_authenticate(self):
        with patch("plataforma.auth_limits.consume_attempt", side_effect=DatabaseError):
            with self.assertLogs("plataforma.auth_limits", level="ERROR"):
                response = self.client.post("/entrar/", {"username": self.user.username, "password": "Senha-forte-123"},
                                            HTTP_HOST="palaciomental.com.br")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_get_does_not_consume_attempts(self):
        self.client.get("/entrar/", HTTP_HOST="palaciomental.com.br")
        self.assertFalse(AuthAttemptWindow.objects.exists())


@skipUnless(connection.vendor == "postgresql", "Concorrência exige PostgreSQL")
class ConcurrentAuthLimitTests(TransactionTestCase):
    def test_parallel_requests_cannot_exceed_account_limit(self):
        for _ in range(9):
            consume_attempt("login", "person", "192.0.2.1")
        barrier = Barrier(2)

        def attempt(number):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return consume_attempt("login", "person", f"192.0.2.{number + 2}")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, range(2)))
        self.assertEqual(sum(value == 0 for value in results), 1)
        self.assertEqual(sum(value > 0 for value in results), 1)
