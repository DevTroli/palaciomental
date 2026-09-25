from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch
from .models import WaitlistEntry


class WaitlistModelTests(TestCase):
    """Testes essenciais do modelo WaitlistEntry."""

    def test_create_waitlist_entry(self):
        """Deve criar entrada com todos os campos obrigatórios."""
        entry = WaitlistEntry.objects.create(
            nome="João Silva",
            telefone="(11) 99999-9999",
            email="joao@email.com",
            consent=True
        )
        self.assertEqual(entry.nome, "João Silva")
        self.assertEqual(entry.email, "joao@email.com")
        self.assertTrue(entry.consent)
        self.assertIsNotNone(entry.created_at)


class WaitlistViewTests(TestCase):
    """A homepage core é a porta de entrada do produto."""

    def test_get_index_returns_200_with_form(self):
        """GET na home deve retornar 200 com formulário."""
        response = self.client.get(reverse("core:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")
        self.assertContains(response, "Últimos projetos abertos")
        self.assertContains(response, "Criar um projeto")


class StatusViewTests(TestCase):
    """A página pública deve ser útil mesmo quando a API externa falha."""

    @patch("listaEspera.views.urlopen")
    def test_status_page_renders_all_services_from_api(self, mock_urlopen):
        response_body = b'{"status":"operacional","checked_at":"2026-09-23T10:15:00Z","deployment":{"commit":"abcdef1234567890","author":"Pablo Troli","branch":"main","service":"django","environment":"production"},"dependencies":{"database":{"status":"operacional"},"django_app":{"status":"degradado"}}}'
        response = mock_urlopen.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = response_body

        response = self.client.get(reverse("listaEspera:status"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "status.html")
        self.assertContains(response, "Banco de dados")
        self.assertContains(response, "Aplicação web")
        self.assertContains(response, "API de status")
        self.assertContains(response, "Instabilidade")
        self.assertContains(response, "abcdef123456")
        self.assertContains(response, "Pablo Troli")

    @patch("listaEspera.views.urlopen", side_effect=TimeoutError)
    def test_status_page_does_not_break_when_api_is_unavailable(self, mock_urlopen):
        response = self.client.get(reverse("listaEspera:status"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Status indisponível no momento")
        self.assertContains(response, "Não foi possível verificar este serviço agora.")
        self.assertContains(response, "Deploy atual")
        self.assertEqual(self.client.get("/status/").status_code, 200)


class WaitlistSubmitTests(TestCase):
    """Testes críticos da view waitlist_submit (POST /lista-espera/)."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("listaEspera:waitlist_submit")
        self.valid_data = {
            "nome": "Carlos Oliveira",
            "telefone": "(31) 77777-7777",
            "email": "carlos@email.com",
            "consent": "on",
        }

    # --- Happy path ---
    def test_post_valid_creates_entry(self):
        """POST válido retorna success=True e cria registro no banco."""
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertTrue(WaitlistEntry.objects.filter(email="carlos@email.com").exists())

    # --- Validação essencial ---
    def test_post_missing_required_returns_400(self):
        """Campos obrigatórios ausentes retornam erro 400."""
        for field in ["nome", "telefone", "email", "consent"]:
            data = self.valid_data.copy()
            data[field] = ""
            response = self.client.post(self.url, data)
            self.assertEqual(response.status_code, 400, f"Field {field} should fail")
            self.assertFalse(response.json()["success"])

    # --- Duplicata ---
    def test_post_duplicate_email_returns_400(self):
        """Email duplicado retorna erro 400 e não cria segundo registro."""
        self.client.post(self.url, self.valid_data)
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertEqual(WaitlistEntry.objects.count(), 1)

    # --- Métodos não permitidos ---
    def test_get_not_allowed(self):
        """GET no endpoint POST retorna 405."""
        self.assertEqual(self.client.get(self.url).status_code, 405)


class WaitlistAdminIntegrationTest(TestCase):
    """Teste de integração básico do admin."""

    def setUp(self):
        self.client = Client()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="pass"
        )
        self.client.login(username="admin", password="pass")
        self.entry = WaitlistEntry.objects.create(
            nome="Admin Test", telefone="(11) 99999-9999",
            email="admin@test.com", consent=True
        )

    def test_admin_changelist_shows_entries(self):
        """Admin listagem deve exibir entradas cadastradas."""
        response = self.client.get(reverse("admin:listaEspera_waitlistentry_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Test")
