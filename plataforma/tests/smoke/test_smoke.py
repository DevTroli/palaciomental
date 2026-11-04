from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class HomepageTests(TestCase):
    def test_root_returns_product_home(self):
        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")
        self.assertContains(response, "Dê continuidade às suas ideias.")


class StatusViewTests(TestCase):
    """A página pública deve continuar útil quando a API externa falha."""

    @patch("plataforma.views.urlopen")
    def test_status_page_renders_all_services_from_api(self, mock_urlopen):
        response_body = b'{"status":"operacional","checked_at":"2026-09-23T10:15:00Z","deployment":{"commit":"abcdef1234567890","author":"Pablo Troli","branch":"main","service":"django","environment":"production"},"dependencies":{"database":{"status":"operacional"},"django_app":{"status":"degradado"}}}'
        response = mock_urlopen.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = response_body

        response = self.client.get(reverse("plataforma:status"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "status.html")
        self.assertContains(response, "Banco de dados")
        self.assertContains(response, "Aplicação web")
        self.assertContains(response, "API de status")
        self.assertContains(response, "Instabilidade")
        self.assertContains(response, "abcdef123456")
        self.assertContains(response, "Pablo Troli")

    @patch("plataforma.views.urlopen", side_effect=TimeoutError)
    def test_status_page_does_not_break_when_api_is_unavailable(self, mock_urlopen):
        response = self.client.get(reverse("plataforma:status"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Status indisponível no momento")
        self.assertContains(response, "Não foi possível verificar este serviço agora.")
        self.assertContains(response, "Deploy atual")
        self.assertEqual(self.client.get("/status/").status_code, 200)
