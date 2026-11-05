"""Decisão aprovada: "next" aceita só caminho local, com fallback fixo."""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from plataforma.views import _safe_local_next

User = get_user_model()

REJEITADOS = (
    "",
    "https://evil.example/",
    "http://evil.example/",
    "//evil.example/",
    "///evil.example/",
    "/\\evil.example/",
    "\\\\evil.example/",
    "\\evil.example",
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "data:text/html,oi",
    "https://testserver/projetos/",
    "projetos/",
    " //evil.example/",
    "\x00/projetos/",
)
ACEITOS = ("/projetos/", "/projetos/12/?aba=marcos", "/gestao/")


class SafeLocalNextTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/", HTTP_HOST="testserver")

    def test_rejeita_outros_hosts_esquemas_e_ambiguidades(self):
        for valor in REJEITADOS:
            with self.subTest(next=valor):
                self.assertEqual(_safe_local_next(self.request, valor), "")

    def test_aceita_somente_caminho_local(self):
        for valor in ACEITOS:
            with self.subTest(next=valor):
                self.assertEqual(_safe_local_next(self.request, valor), valor)


class LoginGlobalFallbackTests(TestCase):
    def setUp(self):
        User.objects.create_user(username="ana", email="ana@example.com", password="Senha-forte-123")

    def test_url_absoluta_do_proprio_host_cai_no_fallback(self):
        url = reverse("plataforma:login") + "?next=https://testserver/perfil/"
        response = self.client.post(url, {"username": "ana", "password": "Senha-forte-123"})
        self.assertRedirects(response, reverse("plataforma:projects"), fetch_redirect_response=False)

    def test_caminho_local_e_respeitado(self):
        url = reverse("plataforma:login") + "?next=/projetos/novo/"
        response = self.client.post(url, {"username": "ana", "password": "Senha-forte-123"})
        self.assertEqual(response["Location"], "/projetos/novo/")
