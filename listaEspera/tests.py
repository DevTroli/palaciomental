from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import WaitlistEntry


class WaitlistModelTests(TestCase):
    """Testes do modelo WaitlistEntry."""

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

    def test_str_representation(self):
        """__str__ deve retornar nome e email."""
        entry = WaitlistEntry.objects.create(
            nome="Maria Santos",
            telefone="(21) 88888-8888",
            email="maria@email.com",
            consent=True
        )
        self.assertEqual(str(entry), "Maria Santos (maria@email.com)")

    def test_ordering_by_created_at_desc(self):
        """Ordenação padrão deve ser por created_at decrescente."""
        WaitlistEntry.objects.create(
            nome="A", telefone="(11) 11111-1111", email="a@email.com", consent=True
        )
        WaitlistEntry.objects.create(
            nome="B", telefone="(22) 22222-2222", email="b@email.com", consent=True
        )
        entries = list(WaitlistEntry.objects.all())
        self.assertEqual(entries[0].nome, "B")  # Mais recente primeiro
        self.assertEqual(entries[1].nome, "A")


class WaitlistViewTests(TestCase):
    """Testes da view index (GET /)."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("listaEspera:index")

    def test_get_index_returns_200(self):
        """GET na home deve retornar 200."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_index_uses_correct_template(self):
        """Deve usar template listaEspera/index.html."""
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "listaEspera/index.html")

    def test_get_index_contains_form(self):
        """Página deve conter o formulário de waitlist."""
        response = self.client.get(self.url)
        self.assertContains(response, 'id="waitlistForm"')
        self.assertContains(response, 'name="nome"')
        self.assertContains(response, 'name="telefone"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="consent"')


class WaitlistSubmitTests(TestCase):
    """Testes da view waitlist_submit (POST /lista-espera/)."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("listaEspera:waitlist_submit")
        self.valid_data = {
            "nome": "Carlos Oliveira",
            "telefone": "(31) 77777-7777",
            "email": "carlos@email.com",
            "consent": "on",
            "csrfmiddlewaretoken": "test-token",
        }

    # --- Casos de sucesso ---

    def test_post_valid_data_returns_200_and_creates_entry(self):
        """POST válido deve retornar success=True e criar registro."""
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(WaitlistEntry.objects.filter(email="carlos@email.com").exists())

    def test_post_creates_entry_with_correct_fields(self):
        """Registro criado deve ter todos os campos preenchidos."""
        self.client.post(self.url, self.valid_data)
        entry = WaitlistEntry.objects.get(email="carlos@email.com")
        self.assertEqual(entry.nome, "Carlos Oliveira")
        self.assertEqual(entry.telefone, "(31) 77777-7777")
        self.assertEqual(entry.email, "carlos@email.com")
        self.assertTrue(entry.consent)

    def test_post_email_normalized_to_lowercase(self):
        """Email deve ser salvo em lowercase."""
        data = self.valid_data.copy()
        data["email"] = "CARLOS@EMAIL.COM"
        self.client.post(self.url, data)
        entry = WaitlistEntry.objects.get(email="carlos@email.com")
        self.assertEqual(entry.email, "carlos@email.com")

    # --- Validação de campos obrigatórios ---

    def test_post_missing_nome_returns_400(self):
        """Nome ausente deve retornar erro 400."""
        data = self.valid_data.copy()
        data["nome"] = ""
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertIn("obrigatórios", response.json()["error"])

    def test_post_missing_telefone_returns_400(self):
        """Telefone ausente deve retornar erro 400."""
        data = self.valid_data.copy()
        data["telefone"] = ""
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_post_missing_email_returns_400(self):
        """Email ausente deve retornar erro 400."""
        data = self.valid_data.copy()
        data["email"] = ""
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_post_missing_consent_returns_400(self):
        """Consent ausente deve retornar erro 400."""
        data = self.valid_data.copy()
        data["consent"] = ""  # Checkbox não marcado não envia valor
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertIn("Consentimento", response.json()["error"])

    def test_post_consent_false_returns_400(self):
        """Consent='off' deve retornar erro 400."""
        data = self.valid_data.copy()
        data["consent"] = "off"
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    # --- Duplicata ---

    def test_post_duplicate_email_returns_400(self):
        """Email duplicado deve retornar erro 400."""
        self.client.post(self.url, self.valid_data)
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertIn("já está cadastrado", response.json()["error"])
        # Deve ter apenas 1 registro no banco
        self.assertEqual(WaitlistEntry.objects.count(), 1)

    # --- Métodos HTTP não permitidos ---

    def test_get_not_allowed(self):
        """GET não deve ser permitido (405)."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_put_not_allowed(self):
        """PUT não deve ser permitido (405)."""
        response = self.client.put(self.url, {})
        self.assertEqual(response.status_code, 405)

    def test_delete_not_allowed(self):
        """DELETE não deve ser permitido (405)."""
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 405)


class WaitlistAdminTests(TestCase):
    """Testes do admin (integração básica)."""

    def setUp(self):
        self.client = Client()
        # Cria superuser para acessar admin
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="pass"
        )
        self.client.login(username="admin", password="pass")
        self.entry = WaitlistEntry.objects.create(
            nome="Admin Test",
            telefone="(11) 99999-9999",
            email="admin@test.com",
            consent=True
        )

    def test_admin_changelist_accessible(self):
        """Changelist do admin deve ser acessível."""
        url = reverse("admin:listaEspera_waitlistentry_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_changelist_shows_entry(self):
        """Changelist deve mostrar a entrada criada."""
        url = reverse("admin:listaEspera_waitlistentry_changelist")
        response = self.client.get(url)
        self.assertContains(response, "Admin Test")
        self.assertContains(response, "admin@test.com")

    def test_admin_change_form_accessible(self):
        """Form de edição no admin deve ser acessível."""
        url = reverse("admin:listaEspera_waitlistentry_change", args=[self.entry.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_search_works(self):
        """Busca no admin deve funcionar."""
        url = reverse("admin:listaEspera_waitlistentry_changelist")
        response = self.client.get(url, {"q": "Admin Test"})
        self.assertContains(response, "Admin Test")