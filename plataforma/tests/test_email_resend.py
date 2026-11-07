from email.message import Message

import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives, get_connection
from django.test import SimpleTestCase, override_settings

from plataforma.email_backends import EmailDeliveryError


@override_settings(
    EMAIL_BACKEND="plataforma.email_backends.ResendEmailBackend",
    RESEND_API_KEY="test-key-not-a-real-secret",
    RESEND_TIMEOUT=4,
)
class ResendBackendTests(SimpleTestCase):
    def email(self):
        message = EmailMultiAlternatives(
            subject="Convite institucional", body="Versão texto",
            from_email="Palácio Mental <convites@example.com>",
            to=["recipient@example.com"], reply_to=["help@example.com"],
            headers={"Idempotency-Key": "invitation/test-id"},
        )
        message.attach_alternative("<p>Versão HTML</p>", "text/html")
        return message

    @patch("plataforma.email_backends.urlopen")
    def test_sends_text_and_html_via_https_with_timeout_and_idempotency(self, transport):
        transport.return_value.__enter__.return_value = BytesIO(b'{"id":"provider-message-id"}')
        self.assertEqual(self.email().send(), 1)
        request = transport.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.resend.com/emails")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key-not-a-real-secret")
        self.assertEqual(request.get_header("Idempotency-key"), "invitation/test-id")
        self.assertEqual(transport.call_args.kwargs["timeout"], 4)
        payload = json.loads(request.data)
        self.assertEqual(payload["to"], ["recipient@example.com"])
        self.assertEqual(payload["text"], "Versão texto")
        self.assertEqual(payload["html"], "<p>Versão HTML</p>")
        self.assertEqual(payload["reply_to"], ["help@example.com"])

    @override_settings(RESEND_API_KEY="")
    @patch("plataforma.email_backends.urlopen")
    def test_missing_key_fails_before_network_call(self, transport):
        with self.assertRaises(ImproperlyConfigured):
            self.email().send()
        transport.assert_not_called()

    @patch("plataforma.email_backends.urlopen")
    def test_provider_failure_is_sanitized_for_auth_quota_and_server_errors(self, transport):
        for status in (401, 429, 500):
            transport.side_effect = HTTPError(
                "https://api.resend.com/emails", status,
                "sensitive-provider-response", Message(), None,
            )
            with self.subTest(status=status), self.assertRaises(EmailDeliveryError) as caught:
                self.email().send()
            self.assertNotIn("sensitive-provider-response", str(caught.exception))
            self.assertNotIn("test-key", str(caught.exception))

    @patch("plataforma.email_backends.urlopen", side_effect=URLError("sensitive-network-detail"))
    def test_network_failure_respects_fail_silently(self, transport):
        self.assertEqual(self.email().send(fail_silently=True), 0)
        with self.assertRaises(EmailDeliveryError):
            self.email().send()

    @patch("plataforma.email_backends.urlopen", side_effect=TimeoutError)
    def test_timeout_is_reported_as_delivery_error(self, transport):
        with self.assertRaises(EmailDeliveryError):
            self.email().send()

    @patch("plataforma.email_backends.urlopen")
    def test_malformed_or_unconfirmed_provider_response_is_not_success(self, transport):
        for content in (b"not-json", b"{}", b"[]"):
            transport.return_value.__enter__.return_value = BytesIO(content)
            with self.subTest(content=content), self.assertRaises(EmailDeliveryError):
                self.email().send()

    @patch("plataforma.email_backends.urlopen")
    def test_empty_messages_and_no_recipient_make_no_request(self, transport):
        connection = get_connection()
        self.assertEqual(connection.send_messages(None), 0)
        email = self.email()
        email.to = []
        self.assertEqual(connection.send_messages([email]), 0)
        transport.assert_not_called()

    @patch("plataforma.email_backends.urlopen")
    def test_unsupported_attachment_is_not_silently_dropped(self, transport):
        email = self.email()
        email.attach("note.txt", "Conteúdo", "text/plain")
        with self.assertRaises(EmailDeliveryError):
            email.send()
        transport.assert_not_called()
