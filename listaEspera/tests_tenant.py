from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import DominioOrganizacao, MembroOrganizacao, Organizacao


User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=["testserver", ".palaciomental.com.br"],
    PALACIO_BASE_DOMAIN="palaciomental.com.br",
    TENANT_RESERVED_HOSTS=["www", "api", "status", "admin", "app"],
)
class TenantResolutionTests(TestCase):
    def setUp(self):
        self.organization = Organizacao.objects.create(slug="camppg", nome="CAMPPG")
        DominioOrganizacao.objects.create(
            organizacao=self.organization,
            hostname="camppg.palaciomental.com.br",
            principal=True,
        )
        self.user = User.objects.create_user(
            username="participante",
            email="participante@example.com",
            password="Senha-forte-123",
        )

    def test_base_domain_remains_public(self):
        response = self.client.get("/", HTTP_HOST="palaciomental.com.br")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dê continuidade às suas ideias.")

    def test_tenant_requires_authentication(self):
        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")

        self.assertRedirects(
            response,
            f"{reverse('listaEspera:login')}?next=/",
            fetch_redirect_response=False,
        )

    def test_tenant_auth_page_is_available_before_affiliation(self):
        response = self.client.get(
            reverse("listaEspera:login"),
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrar")

    def test_authenticated_user_without_affiliation_is_forbidden(self):
        self.client.force_login(self.user)

        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "afiliação ativa", status_code=403)

    def test_active_affiliation_can_enter_resolved_tenant(self):
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        self.client.force_login(self.user)

        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dê continuidade às suas ideias.")

    def test_unknown_subdomain_does_not_fall_back_to_another_tenant(self):
        response = self.client.get("/", HTTP_HOST="outra.palaciomental.com.br")

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "CAMPPG", status_code=404)
