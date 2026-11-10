import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import TypedDict
from threading import Barrier
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import close_old_connections, connection, connections
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from plataforma.email_backends import EmailDeliveryError
from plataforma.models import (
    ConviteGrupo, ConviteOrganizacao, DominioOrganizacao, MemberProfile,
    MembroGrupo, MembroOrganizacao, MembroTurma, Organizacao, ProgramaInstitucional,
)

from .base import PortalInstitucionalBase


User = get_user_model()
HOST = "camppg.palaciomental.com.br"
PASSWORD = "Senha-convidado-forte-2026"


class InvitationOverrides(TypedDict, total=False):
    expira_em: datetime
    status: str


class OnboardingConvitesTests(PortalInstitucionalBase):
    def make_invitation(self, kind="organization", email="novo@example.com", **kwargs):
        token = secrets.token_urlsafe(32)
        fields = {
            "convidado_por": self.user,
            "email": email,
            "hash_token": hashlib.sha256(token.encode()).hexdigest(),
            "expira_em": timezone.now() + timedelta(days=7),
            **kwargs,
        }
        if kind == "group":
            program = ProgramaInstitucional.objects.create(
                organizacao=self.organization, nome="Programa", slug="programa",
                criado_por=self.user,
            )
            group = self.make_group(program, "Grupo")
            invitation = ConviteGrupo.objects.create(grupo=group, **fields)
            name = "institutional_invite_accept"
        else:
            invitation = ConviteOrganizacao.objects.create(
                organizacao=self.organization, papel="professor", **fields,
            )
            name = "institutional_organization_invite_accept"
        return invitation, reverse(f"plataforma:{name}", kwargs={"token": token})

    def register(self, path, **overrides):
        return self.client.post(path, {
            "action": "register", "username": "novo-convidado", "first_name": "Novo",
            "email": "atacante@example.com", "password1": PASSWORD,
            "password2": PASSWORD, "is_staff": "on", "is_superuser": "on", **overrides,
        }, HTTP_HOST=HOST)

    def login_for_invitation(self, path, user):
        return self.client.post(
            reverse("plataforma:login") + "?" + urlencode({"next": path}),
            {"username": user.username, "password": PASSWORD},
            HTTP_HOST=HOST,
        )

    def test_new_user_registers_then_explicitly_accepts_for_both_kinds(self):
        for kind in ("organization", "group"):
            with self.subTest(kind=kind):
                self.client.logout()
                email = f"{kind}@example.com"
                invitation, path = self.make_invitation(kind, email=email)
                response = self.client.get(path, HTTP_HOST=HOST)
                self.assertContains(response, "Criar conta e continuar")
                self.assertEqual(response["Referrer-Policy"], "strict-origin")
                self.assertIn("no-store", response["Cache-Control"])
                self.assertNotContains(response, "Criar projeto institucional")
                username = f"novo-{kind}"
                response = self.register(path, username=username)
                self.assertRedirects(response, path, fetch_redirect_response=False)
                user = User.objects.get(username=username)
                self.assertEqual(user.email, email)
                self.assertTrue(user.check_password(PASSWORD))
                self.assertTrue(MemberProfile.objects.filter(user=user).exists())
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)
                self.assertFalse(MembroOrganizacao.objects.filter(usuario=user).exists())
                self.assertEqual(self.client.get("/", HTTP_HOST=HOST).status_code, 403)
                response = self.client.get(path, HTTP_HOST=HOST)
                self.assertContains(response, "Aceitar convite e entrar")
                invitation.refresh_from_db()
                self.assertEqual(invitation.status, "pendente")
                response = self.client.post(path, {"action": "accept"}, HTTP_HOST=HOST)
                self.assertEqual(response.status_code, 302)
                affiliation = MembroOrganizacao.objects.get(usuario=user, organizacao=self.organization)
                self.assertEqual(affiliation.papel, "membro" if kind == "group" else "professor")
                if kind == "group":
                    assert isinstance(invitation, ConviteGrupo)
                    self.assertTrue(MembroGrupo.objects.filter(grupo=invitation.grupo, usuario=user).exists())
                    self.assertTrue(MembroTurma.objects.filter(turma=invitation.grupo.turma, usuario=user).exists())
                self.assertEqual(self.client.get("/", HTTP_HOST=HOST).status_code, 200)
                invitation.refresh_from_db()
                self.assertEqual(invitation.status, "aceito")
                self.assertEqual(self.client.post(path, {"action": "accept"}, HTTP_HOST=HOST).status_code, 403)

    def test_existing_user_real_login_returns_to_invitation_without_affiliation(self):
        for kind in ("organization", "group"):
            with self.subTest(kind=kind):
                self.client.logout()
                user = User.objects.create_user(
                    username=f"existente-{kind}", email=f"{kind}@example.com", password=PASSWORD,
                )
                invitation, path = self.make_invitation(kind, email=user.email)
                response = self.login_for_invitation(path, user)
                self.assertRedirects(response, path, fetch_redirect_response=False)
                self.assertContains(self.client.get(path, HTTP_HOST=HOST), "Aceitar convite e entrar")
                self.assertFalse(MembroOrganizacao.objects.filter(usuario=user).exists())
                self.assertEqual(self.client.get("/", HTTP_HOST=HOST).status_code, 403)
                invitation.refresh_from_db()
                self.assertEqual(invitation.status, "pendente")
                self.assertEqual(self.client.post(path, {"action": "accept"}, HTTP_HOST=HOST).status_code, 302)
                self.assertTrue(MembroOrganizacao.objects.filter(usuario=user).exists())

    def test_get_never_accepts_even_for_authenticated_recipient(self):
        invitation, path = self.make_invitation()
        User.objects.create_user(username="novo", email=invitation.email, password=PASSWORD)
        self.client.post(reverse("plataforma:login"), {"username": "novo", "password": PASSWORD}, HTTP_HOST=HOST)
        self.assertContains(self.client.get(path, HTTP_HOST=HOST), "Aceitar convite e entrar")
        self.assertFalse(MembroOrganizacao.objects.filter(usuario__username="novo").exists())
        invitation.refresh_from_db()
        self.assertIsNone(invitation.aceito_em)

    def test_expired_revoked_or_invalid_token_cannot_register(self):
        invalid_states: tuple[InvitationOverrides, ...] = (
            {"expira_em": timezone.now() - timedelta(seconds=1)},
            {"status": "revogado"},
            {"status": "aceito"},
        )
        for fields in invalid_states:
            expiry, status = fields.get("expira_em"), fields.get("status")
            if expiry is not None:
                invitation, path = self.make_invitation(expira_em=expiry)
            else:
                assert status is not None
                invitation, path = self.make_invitation(status=status)
            self.assertEqual(self.register(path).status_code, 403)
            self.assertFalse(User.objects.filter(username="novo-convidado").exists())
            invitation.refresh_from_db()
            self.assertIsNone(invitation.aceito_em)
        self.assertEqual(self.register("/convites/organizacao/invalido/aceitar/").status_code, 404)

    def test_wrong_host_or_global_cannot_register_or_accept(self):
        _, path = self.make_invitation()
        organization = Organizacao.objects.create(nome="Outra", slug="outra", status="ativa")
        DominioOrganizacao.objects.create(organizacao=organization, hostname="outra.palaciomental.com.br", principal=True)
        for host in ("palaciomental.com.br", "outra.palaciomental.com.br"):
            for method in ("get", "post"):
                response = getattr(self.client, method)(path, HTTP_HOST=host)
                self.assertEqual(response.status_code, 404)
        self.assertFalse(MembroOrganizacao.objects.filter(usuario__username="novo-convidado").exists())

    def test_existing_email_cannot_be_recreated_through_invite(self):
        self.make_existing_recipient()
        _, path = self.make_invitation()
        response = self.register(path)
        self.assertContains(response, "Este e-mail já está cadastrado.")
        self.assertFalse(User.objects.filter(username="novo-convidado").exists())

    def make_existing_recipient(self):
        return User.objects.create_user(username="existente", email="novo@example.com", password=PASSWORD)

    def test_wrong_email_cannot_accept_or_use_invitation_login_exception(self):
        _, path = self.make_invitation()
        user = User.objects.create_user(username="outro", email="outro@example.com", password=PASSWORD)
        self.assertEqual(self.login_for_invitation(path, user).status_code, 403)
        self.assertEqual(self.client.get(path, HTTP_HOST=HOST).status_code, 403)
        self.assertEqual(self.client.post(path, {"action": "accept"}, HTTP_HOST=HOST).status_code, 403)
        self.assertFalse(MembroOrganizacao.objects.filter(usuario=user).exists())

    def test_login_exception_does_not_allow_arbitrary_next(self):
        user = self.make_existing_recipient()
        for path in ("/gestao/", "//evil.example/", "/convites/organizacao/invalido/aceitar/"):
            self.client.logout()
            self.assertEqual(self.login_for_invitation(path, user).status_code, 403)

    def test_register_without_invite_stays_closed_in_tenant(self):
        self.assertEqual(self.client.get(reverse("plataforma:register"), HTTP_HOST=HOST).status_code, 403)
        self.assertEqual(self.client.post(reverse("plataforma:register"), {}, HTTP_HOST=HOST).status_code, 403)

    def test_global_registration_still_does_not_grant_tenant_access(self):
        response = self.client.post(reverse("plataforma:register"), {
            "first_name": "Pessoal", "username": "pessoal", "email": "pessoal@example.com",
            "password1": PASSWORD, "password2": PASSWORD,
        }, HTTP_HOST="palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MembroOrganizacao.objects.filter(usuario__username="pessoal").exists())
        self.assertEqual(self.client.get("/", HTTP_HOST=HOST).status_code, 403)

    def test_accept_requires_csrf_and_valid_action(self):
        _, path = self.make_invitation()
        client = Client(enforce_csrf_checks=True)
        page = client.get(path, HTTP_HOST=HOST)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(client.post(path, {"action": "register"}, HTTP_HOST=HOST).status_code, 403)
        response = client.post(path, {
            "action": "register", "first_name": "Novo", "username": "csrf-user",
            "password1": PASSWORD, "password2": PASSWORD,
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        }, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 302)
        client.get(path, HTTP_HOST=HOST)
        self.assertEqual(client.post(path, {"action": "accept"}, HTTP_HOST=HOST).status_code, 403)
        response = client.post(path, {
            "action": "accept", "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        }, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 302)
        _, another_path = self.make_invitation(email="another@example.com")
        self.assertEqual(self.client.post(another_path, {"action": "accept"}, HTTP_HOST=HOST).status_code, 400)

    def test_invitation_revoked_after_registration_cannot_be_accepted(self):
        invitation, path = self.make_invitation()
        self.register(path)
        invitation.status = "revogado"
        invitation.save(update_fields=["status"])
        self.assertEqual(self.client.post(path, {"action": "accept"}, HTTP_HOST=HOST).status_code, 403)
        self.assertFalse(MembroOrganizacao.objects.filter(usuario__username="novo-convidado").exists())

    def test_group_invitation_does_not_bypass_suspended_affiliation(self):
        invitation, path = self.make_invitation("group")
        user = self.make_existing_recipient()
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=user, status="suspensa")
        self.login_for_invitation(path, user)
        self.assertEqual(self.client.post(path, {"action": "accept"}, HTTP_HOST=HOST).status_code, 403)
        self.assertFalse(MembroGrupo.objects.filter(usuario=user).exists())
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "pendente")

    @patch("plataforma.views._send_organization_invitation_email", side_effect=EmailDeliveryError("Falha simulada"))
    def test_delivery_failure_preserves_revocable_invite_without_server_error(self, sender):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel="gestor")
        self.client.post(reverse("plataforma:login"), {
            "username": self.user.username, "password": "Senha-forte-123",
        }, HTTP_HOST=HOST)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("plataforma:institutional_members"), {
                "acao": "convidar", "email": "novo@example.com", "papel": "membro",
            }, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 302)
        sender.assert_called_once()
        self.assertTrue(ConviteOrganizacao.objects.filter(email="novo@example.com", status="pendente").exists())
        feedback = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(any("envio do e-mail falhou" in message for message in feedback))
        self.assertFalse(any("encaminhado para envio" in message for message in feedback))


@override_settings(ALLOWED_HOSTS=[".palaciomental.com.br"])
class ConviteConcorrenteTests(TransactionTestCase):
    def test_two_simultaneous_acceptances_consume_one_token_once(self):
        if connection.vendor != "postgresql":
            self.skipTest("A concorrência e o bloqueio de linha exigem PostgreSQL.")
        organization = Organizacao.objects.create(nome="CAMPPG", slug="camppg", status="ativa")
        DominioOrganizacao.objects.create(organizacao=organization, hostname=HOST, principal=True)
        user = User.objects.create_user(username="concorrente", email="novo@example.com", password=PASSWORD)
        token = secrets.token_urlsafe(32)
        invitation = ConviteOrganizacao.objects.create(
            organizacao=organization, convidado_por=user, email=user.email,
            papel="membro", hash_token=hashlib.sha256(token.encode()).hexdigest(),
            expira_em=timezone.now() + timedelta(days=7),
        )
        path = reverse("plataforma:institutional_organization_invite_accept", kwargs={"token": token})
        barrier = Barrier(2, timeout=15)

        def accept():
            close_old_connections()
            try:
                client = Client()
                login_response = client.post(
                    reverse("plataforma:login") + "?" + urlencode({"next": path}),
                    {"username": user.username, "password": PASSWORD}, HTTP_HOST=HOST,
                )
                self.assertEqual(login_response.status_code, 302)
                barrier.wait()
                return client.post(path, {"action": "accept"}, HTTP_HOST=HOST).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(accept) for _ in range(2)]
            statuses = [future.result(timeout=30) for future in futures]
        self.assertCountEqual(statuses, [302, 403])
        self.assertEqual(MembroOrganizacao.objects.filter(usuario=user).count(), 1)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "aceito")
