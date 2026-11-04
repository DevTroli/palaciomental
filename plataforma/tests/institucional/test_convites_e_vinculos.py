import hashlib
from io import BytesIO
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from plataforma.models import ConviteGrupo, ConviteOrganizacao, DominioOrganizacao, Grupo, IdentidadeOrganizacao, MembroGrupo, MembroOrganizacao, MembroTurma, Organizacao, ProgramaInstitucional, Project, SolicitacaoGrupo, SolicitacaoTurma, Turma, VinculoProjetoInstitucional
from plataforma.services import ativar_organizacao


User = get_user_model()


from .base import PortalInstitucionalBase


class ConvitesEVinculosTests(PortalInstitucionalBase):
    def test_group_invitation_acceptance_creates_affiliation_and_membership(self):
        manager = self.user
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=manager,
            papel=MembroOrganizacao.PAPEL_GESTOR,
        )
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa CAMPPG",
            slug="programa-camppg",
            criado_por=manager,
        )
        grupo = self.make_group(programa, "Turma 2026", criado_por=manager)
        invited = User.objects.create_user(username="convidado", email="convidado@example.com", password="Senha-forte-123")
        raw_token = secrets.token_urlsafe(24)
        invite = ConviteGrupo.objects.create(
            grupo=grupo,
            convidado_por=manager,
            email=invited.email,
            papel="membro",
            hash_token=hashlib.sha256(raw_token.encode()).hexdigest(),
            expira_em=timezone.now() + timedelta(days=7),
        )

        response = self.client.get(
            reverse("plataforma:institutional_invite_accept", kwargs={"token": raw_token}),
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertRedirects(response, f"{reverse('plataforma:login')}?next={reverse('plataforma:institutional_invite_accept', kwargs={'token': raw_token})}", fetch_redirect_response=False)

        self.client.force_login(invited)
        response = self.client.get(
            reverse("plataforma:institutional_invite_accept", kwargs={"token": raw_token}),
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertRedirects(response, reverse("plataforma:institutional_program_detail", kwargs={"programa_id": programa.pk}), fetch_redirect_response=False)
        self.assertTrue(MembroOrganizacao.objects.filter(organizacao=self.organization, usuario=invited, papel=MembroOrganizacao.PAPEL_MEMBRO).exists())
        self.assertTrue(MembroGrupo.objects.filter(grupo=grupo, usuario=invited, status=MembroGrupo.STATUS_ATIVO).exists())
        invite.refresh_from_db()
        self.assertEqual(invite.status, ConviteGrupo.STATUS_ACEITO)

    def test_expired_group_invitation_is_rejected(self):
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa expirado",
            slug="programa-expirado",
            criado_por=self.user,
        )
        grupo = self.make_group(programa, "Grupo expirado")
        raw_token = secrets.token_urlsafe(24)
        ConviteGrupo.objects.create(
            grupo=grupo,
            convidado_por=self.user,
            email=self.user.email,
            hash_token=hashlib.sha256(raw_token.encode()).hexdigest(),
            expira_em=timezone.now() - timedelta(minutes=1),
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("plataforma:institutional_invite_accept", kwargs={"token": raw_token}),
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertEqual(response.status_code, 403)

    def test_regular_member_cannot_manage_affiliations_or_invite(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("plataforma:institutional_members"), HTTP_HOST="camppg.palaciomental.com.br").status_code, 403)
        response = self.client.get(reverse("plataforma:institutional_management"), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 403)

    def test_professor_can_invite_only_when_assigned_to_group(self):
        professor = User.objects.create_user(username="professor", email="professor@example.com", password="Senha-forte-123")
        target = User.objects.create_user(username="aluno", email="aluno@example.com", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=professor, papel=MembroOrganizacao.PAPEL_PROFESSOR)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa professores", slug="programa-professores", criado_por=professor)
        grupo = self.make_group(programa, "Grupo orientado", criado_por=professor, professor=professor)
        self.client.force_login(professor)
        response = self.client.post(reverse("plataforma:institutional_group_members", kwargs={"group_id": grupo.pk}), {"email": target.email, "papel": "membro"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ConviteGrupo.objects.filter(grupo=grupo, email=target.email).exists())

    def test_last_owner_cannot_be_suspended_or_demoted(self):
        owner = self.user
        manager = User.objects.create_user(username="gestor", email="gestor@example.com", password="Senha-forte-123")
        owner_affiliation = MembroOrganizacao.objects.create(organizacao=self.organization, usuario=owner, papel=MembroOrganizacao.PAPEL_PROPRIETARIO)
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=manager, papel=MembroOrganizacao.PAPEL_GESTOR)
        self.client.force_login(manager)
        response = self.client.post(reverse("plataforma:institutional_members"), {"membro_id": owner_affiliation.pk, "acao": "suspender"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 403)
        self.client.force_login(owner)
        response = self.client.post(reverse("plataforma:institutional_members"), {"membro_id": owner_affiliation.pk, "acao": "papel", "papel": MembroOrganizacao.PAPEL_MEMBRO}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 400)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_group_invite_sends_html_and_text_email_after_commit(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_GESTOR)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa de e-mail", slug="programa-email", criado_por=self.user)
        grupo = self.make_group(programa, "Grupo de convite")
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("plataforma:institutional_group_members", kwargs={"group_id": grupo.pk}), {"email": "email@example.com", "papel": "membro"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to[0], "email@example.com")
        self.assertEqual(mail.outbox[0].alternatives[0][1], "text/html")
        self.assertIn("Grupo de convite", mail.outbox[0].body)
        self.assertIn("camppg.palaciomental.com.br", mail.outbox[0].alternatives[0][0])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_owner_and_manager_invite_only_allowed_roles(self):
        owner = self.user
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=owner, papel=MembroOrganizacao.PAPEL_PROPRIETARIO)
        self.client.force_login(owner)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("plataforma:institutional_members"),
                {"acao": "convidar", "email": "gestor@example.com", "papel": MembroOrganizacao.PAPEL_GESTOR},
                HTTP_HOST="camppg.palaciomental.com.br",
            )
        self.assertEqual(response.status_code, 302)
        convite = ConviteOrganizacao.objects.get(email="gestor@example.com")
        self.assertEqual(convite.papel, MembroOrganizacao.PAPEL_GESTOR)
        self.assertEqual(mail.outbox[0].to, ["gestor@example.com"])
        self.assertIn("Aceitar convite", mail.outbox[0].alternatives[0][0])

        manager = User.objects.create_user(username="gestor-convidado", email="gestor@example.com", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=manager, papel=MembroOrganizacao.PAPEL_GESTOR)
        self.client.force_login(manager)
        response = self.client.post(
            reverse("plataforma:institutional_members"),
            {"acao": "convidar", "email": "professor@example.com", "papel": MembroOrganizacao.PAPEL_PROFESSOR},
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ConviteOrganizacao.objects.filter(email="professor@example.com", papel=MembroOrganizacao.PAPEL_PROFESSOR).exists())

    def test_manager_cannot_invite_owner_and_member_cannot_use_tenant_invitation(self):
        manager = User.objects.create_user(username="gestor", email="gestor@example.com", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=manager, papel=MembroOrganizacao.PAPEL_GESTOR)
        self.client.force_login(manager)
        response = self.client.post(
            reverse("plataforma:institutional_members"),
            {"acao": "convidar", "email": "owner@example.com", "papel": MembroOrganizacao.PAPEL_PROPRIETARIO},
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ConviteOrganizacao.objects.filter(email="owner@example.com").exists())

        member = User.objects.create_user(username="membro", email="membro@example.com", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=member, papel=MembroOrganizacao.PAPEL_MEMBRO)
        self.client.force_login(member)
        response = self.client.post(
            reverse("plataforma:institutional_members"),
            {"acao": "convidar", "email": "outro@example.com", "papel": MembroOrganizacao.PAPEL_MEMBRO},
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertEqual(response.status_code, 403)

    def test_organization_invitation_acceptance_creates_affiliation_once(self):
        owner = self.user
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=owner, papel=MembroOrganizacao.PAPEL_PROPRIETARIO)
        invited = User.objects.create_user(username="novo-membro", email="novo@example.com", password="Senha-forte-123")
        raw_token = secrets.token_urlsafe(32)
        convite = ConviteOrganizacao.objects.create(
            organizacao=self.organization,
            convidado_por=owner,
            email=invited.email,
            papel=MembroOrganizacao.PAPEL_PROFESSOR,
            hash_token=hashlib.sha256(raw_token.encode()).hexdigest(),
            expira_em=timezone.now() + timedelta(days=7),
        )
        self.client.force_login(invited)
        response = self.client.get(
            reverse("plataforma:institutional_organization_invite_accept", kwargs={"token": raw_token}),
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertRedirects(response, reverse("plataforma:projects"), fetch_redirect_response=False)
        affiliation = MembroOrganizacao.objects.get(organizacao=self.organization, usuario=invited)
        self.assertEqual(affiliation.papel, MembroOrganizacao.PAPEL_PROFESSOR)
        convite.refresh_from_db()
        self.assertEqual(convite.status, ConviteOrganizacao.STATUS_ACEITO)
        self.assertEqual(
            self.client.get(
                reverse("plataforma:institutional_organization_invite_accept", kwargs={"token": raw_token}),
                HTTP_HOST="camppg.palaciomental.com.br",
            ).status_code,
            403,
        )

    def test_expired_or_wrong_email_organization_invitation_is_rejected(self):
        owner = self.user
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=owner, papel=MembroOrganizacao.PAPEL_PROPRIETARIO)
        invited = User.objects.create_user(username="outro", email="outro@example.com", password="Senha-forte-123")
        raw_token = secrets.token_urlsafe(32)
        ConviteOrganizacao.objects.create(
            organizacao=self.organization,
            convidado_por=owner,
            email="destinatario@example.com",
            papel=MembroOrganizacao.PAPEL_MEMBRO,
            hash_token=hashlib.sha256(raw_token.encode()).hexdigest(),
            expira_em=timezone.now() + timedelta(days=7),
        )
        self.client.force_login(invited)
        response = self.client.get(
            reverse("plataforma:institutional_organization_invite_accept", kwargs={"token": raw_token}),
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(MembroOrganizacao.objects.filter(organizacao=self.organization, usuario=invited).exists())

        expired_token = secrets.token_urlsafe(32)
        ConviteOrganizacao.objects.create(
            organizacao=self.organization,
            convidado_por=owner,
            email=invited.email,
            papel=MembroOrganizacao.PAPEL_MEMBRO,
            hash_token=hashlib.sha256(expired_token.encode()).hexdigest(),
            expira_em=timezone.now() - timedelta(minutes=1),
        )
        response = self.client.get(
            reverse("plataforma:institutional_organization_invite_accept", kwargs={"token": expired_token}),
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_can_revoke_pending_organization_invitation(self):
        manager = self.user
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=manager, papel=MembroOrganizacao.PAPEL_GESTOR)
        convite = ConviteOrganizacao.objects.create(
            organizacao=self.organization,
            convidado_por=manager,
            email="revogar@example.com",
            papel=MembroOrganizacao.PAPEL_MEMBRO,
            hash_token="b" * 64,
            expira_em=timezone.now() + timedelta(days=7),
        )
        self.client.force_login(manager)
        response = self.client.post(
            reverse("plataforma:institutional_organization_invite_revoke", kwargs={"invite_id": convite.pk}),
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertEqual(response.status_code, 302)
        convite.refresh_from_db()
        self.assertEqual(convite.status, ConviteOrganizacao.STATUS_REVOGADO)
