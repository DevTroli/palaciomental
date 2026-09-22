from django.test import TestCase, Client
from django.urls import reverse
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
    """Teste essencial da view index (GET /)."""

    def test_get_index_returns_200_with_form(self):
        """GET na home deve retornar 200 com formulário."""
        response = self.client.get(reverse("listaEspera:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "listaEspera/index.html")
        self.assertContains(response, 'id="waitlistForm"')


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