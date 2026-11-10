from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils import timezone

from plataforma.models import MembroOrganizacao
from .base import PortalInstitucionalBase
from . import test_onboarding_convites as onboarding

HOST = onboarding.HOST
PASSWORD = onboarding.PASSWORD
User = get_user_model()


@override_settings(DEBUG=False, CSRF_TRUSTED_ORIGINS=[])
class ConvitesCSRFTests(PortalInstitucionalBase):
    make_invitation = onboarding.OnboardingConvitesTests.make_invitation

    def setUp(self):
        super().setUp()
        self.browser = Client(enforce_csrf_checks=True)
        self.invitation, self.path = self.make_invitation()

    def get_form(self):
        return self.browser.get(self.path, secure=True, HTTP_HOST=HOST)

    def registration(self, **extra):
        return {
            "action": "register", "username": "csrf-convidado",
            "password1": PASSWORD, "password2": PASSWORD,
            "csrfmiddlewaretoken": self.browser.cookies["csrftoken"].value,
            **extra,
        }

    def test_https_without_origin_or_referer_is_still_rejected(self):
        self.get_form()
        response = self.browser.post(self.path, self.registration(), secure=True, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Não foi possível validar este envio", status_code=403)
        self.assertContains(response, "Reabrir formulário", status_code=403)
        self.assertFalse(User.objects.filter(username="csrf-convidado").exists())
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], "strict-origin")

    def test_https_origin_only_referer_allows_registration_and_explicit_accept(self):
        response = self.get_form()
        self.assertEqual(response["Referrer-Policy"], "strict-origin")
        response = self.browser.post(
            self.path, self.registration(email="outro@example.com"),
            secure=True, HTTP_HOST=HOST, HTTP_REFERER=f"https://{HOST}/",
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="csrf-convidado")
        self.assertEqual(user.email, self.invitation.email)
        self.assertEqual(user.first_name, "")
        self.assertFalse(MembroOrganizacao.objects.filter(usuario=user).exists())
        self.assertEqual(self.browser.get("/", secure=True, HTTP_HOST=HOST).status_code, 403)
        self.get_form()
        response = self.browser.post(
            self.path, {"action": "accept", "csrfmiddlewaretoken": self.browser.cookies["csrftoken"].value},
            secure=True, HTTP_HOST=HOST, HTTP_REFERER=f"https://{HOST}/",
        )
        self.assertEqual(response.status_code, 302)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, "aceito")
        self.assertTrue(MembroOrganizacao.objects.filter(usuario=user, organizacao=self.organization).exists())

    def test_valid_origin_is_supported_and_foreign_origin_is_rejected(self):
        self.get_form()
        response = self.browser.post(
            self.path, self.registration(), secure=True, HTTP_HOST=HOST,
            HTTP_ORIGIN="https://attacker.invalid",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="csrf-convidado").exists())
        response = self.browser.post(
            self.path, self.registration(), secure=True, HTTP_HOST=HOST,
            HTTP_ORIGIN=f"https://{HOST}",
        )
        self.assertEqual(response.status_code, 302)

    def test_bad_token_does_not_consume_invitation_or_create_user(self):
        self.get_form()
        response = self.browser.post(
            self.path, self.registration(csrfmiddlewaretoken="invalid"),
            secure=True, HTTP_HOST=HOST, HTTP_REFERER=f"https://{HOST}/",
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "Verificação CSRF falhou", status_code=403)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, "pendente")
        self.assertFalse(User.objects.filter(username="csrf-convidado").exists())

    def test_null_origin_is_rejected_even_with_valid_token(self):
        self.get_form()
        response = self.browser.post(
            self.path, self.registration(), secure=True, HTTP_HOST=HOST,
            HTTP_ORIGIN="null",
        )
        self.assertContains(response, "Não foi possível validar este envio", status_code=403)
        self.assertFalse(User.objects.filter(username="csrf-convidado").exists())
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, "pendente")

    def test_expired_invitation_uses_safe_permission_page(self):
        self.invitation.expira_em = timezone.now() - timedelta(minutes=1)
        self.invitation.save(update_fields=["expira_em"])
        response = self.get_form()
        self.assertContains(response, "Este acesso não está disponível", status_code=403)
        self.assertNotContains(response, "Criar conta e continuar", status_code=403)
        self.assertNotContains(response, "Reabrir formulário", status_code=403)
        self.assertIn("no-store", response["Cache-Control"])

    def test_compact_form_only_has_three_visible_account_fields(self):
        response = self.get_form()
        self.assertContains(response, 'aria-current="step"')
        self.assertContains(response, "Confirmar entrada")
        self.assertContains(response, "Requisitos da senha")
        self.assertNotContains(response, 'name="first_name"')
        self.assertNotContains(response, 'name="email"')
        for field in ("username", "password1", "password2"):
            self.assertContains(response, f'name="{field}"')

    def test_different_passwords_are_rejected_without_affiliation(self):
        self.get_form()
        response = self.browser.post(
            self.path, self.registration(password2="Outra-senha-1234"),
            secure=True, HTTP_HOST=HOST, HTTP_REFERER=f"https://{HOST}/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_password2_error"')
        self.assertFalse(User.objects.filter(username="csrf-convidado").exists())

    def test_csrf_log_does_not_contain_token_or_submitted_password(self):
        self.get_form()
        with self.assertLogs("plataforma.error_views", level="WARNING") as logs:
            self.browser.post(self.path, self.registration(), secure=True, HTTP_HOST=HOST)
        output = "\n".join(logs.output)
        self.assertIn("categoria=referer", output)
        self.assertNotIn(self.path, output)
        self.assertNotIn(PASSWORD, output)
        self.assertNotIn(self.invitation.email, output)
