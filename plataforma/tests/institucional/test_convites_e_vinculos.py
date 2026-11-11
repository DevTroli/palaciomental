from plataforma.tests.email_helpers import html_alternative

from typing import cast
from django.core.mail import EmailMultiAlternatives

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
    def test_member_directory_filters_and_paginates_within_organization(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel="proprietario")
        for index in range(13):
            user = User.objects.create_user(username=f"aluno-{index:02d}")
            MembroOrganizacao.objects.create(organizacao=self.organization, usuario=user, papel="membro")
        self.client.force_login(self.user)
        path = reverse("plataforma:institutional_members")
        host = {"HTTP_HOST": "camppg.palaciomental.com.br"}
        first = self.client.get(path, {"papel": "membro"}, **host)
        self.assertEqual(first.context["membros"].paginator.count, 13)
        self.assertEqual(len(first.context["membros"]), 12)
        self.assertContains(first, "Página 1 de 2")
        self.assertContains(first, 'id="diretorio-membros"')
        self.assertContains(first, "tenant-members.js")
        self.assertContains(first, 'aria-label="Filtrar pessoas por papel ao final da lista"')
        second = self.client.get(path, {"papel": "membro", "pagina": 2}, **host)
        self.assertEqual(len(second.context["membros"]), 1)
        self.assertContains(second, "papel=membro")
        owners = self.client.get(path, {"papel": "proprietario"}, **host)
        self.assertEqual(owners.context["membros"].paginator.count, 1)

    def test_owner_can_invite_all_roles_and_manager_cannot_change_roles(self):
        from plataforma.services import papeis_convidaveis
        self.assertEqual(set(papeis_convidaveis("proprietario")), {"proprietario", "gestor", "professor", "membro"})
        self.assertEqual(set(papeis_convidaveis("gestor")), {"professor", "membro"})
        self.assertEqual(papeis_convidaveis("professor"), ())
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel="proprietario")
        manager = User.objects.create_user(username="manager", email="manager@example.com")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=manager, papel="gestor")
        member = User.objects.create_user(username="student", email="student@example.com")
        affiliation = MembroOrganizacao.objects.create(organizacao=self.organization, usuario=member, papel="membro")
        path = reverse("plataforma:institutional_members")
        self.client.force_login(manager)
        response = self.client.post(path, {"acao": "papel", "membro_id": affiliation.pk, "papel": "professor"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 403)
        affiliation.refresh_from_db()
        self.assertEqual(affiliation.papel, "membro")
        self.client.force_login(self.user)
        response = self.client.post(path, {"acao": "papel", "membro_id": affiliation.pk, "papel": "proprietario"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        affiliation.refresh_from_db()
        self.assertEqual(affiliation.papel, "proprietario")

    def test_owner_invites_all_roles_and_manager_cannot_invite_peers(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel="proprietario")
        self.client.force_login(self.user)
        for role in ("proprietario", "gestor", "professor", "membro"):
            with self.subTest(role=role):
                response = self.client.post(reverse("plataforma:institutional_members"),
                    {"acao": "convidar", "email": role + "@example.com", "papel": role},
                    HTTP_HOST="camppg.palaciomental.com.br")
                self.assertEqual(response.status_code, 302)
                self.assertTrue(ConviteOrganizacao.objects.filter(email=role + "@example.com", papel=role).exists())
        manager = User.objects.create_user(username="manager2", email="manager2@example.com")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=manager, papel="gestor")
        self.client.force_login(manager)
        response = self.client.post(reverse("plataforma:institutional_members"),
            {"acao": "convidar", "email": "peer@example.com", "papel": "gestor"},
            HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ConviteOrganizacao.objects.filter(email="peer@example.com").exists())

    def test_teacher_cannot_invite_to_other_class_or_invite_existing_manager(self):
        teacher = self.user
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=teacher, papel="professor")
        manager = User.objects.create_user(username="higher", email="higher@example.com")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=manager, papel="gestor")
        program = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa", slug="professor-programa", criado_por=teacher)
        own = self.make_group(program, "Própria", professor=teacher)
        other = self.make_group(program, "Outra")
        self.client.force_login(teacher)
        host = {"HTTP_HOST": "camppg.palaciomental.com.br"}
        response = self.client.post(reverse("plataforma:institutional_group_members", args=[own.pk]), {"email": manager.email}, **host)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ConviteGrupo.objects.filter(grupo=own, email=manager.email).exists())
        response = self.client.post(reverse("plataforma:institutional_group_members", args=[other.pk]), {"email": "aluno@example.com"}, **host)
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(ConviteGrupo.objects.filter(grupo=other).exists())

    def test_organization_invite_redirects_by_role(self):
        for role in ("membro", "professor", "gestor", "proprietario"):
            with self.subTest(role=role):
                user = User.objects.create_user(username="invite-" + role, email=role + "@example.com")
                token = secrets.token_urlsafe(32)
                ConviteOrganizacao.objects.create(organizacao=self.organization, convidado_por=self.user,
                    email=user.email, papel=role, hash_token=hashlib.sha256(token.encode()).hexdigest(),
                    expira_em=timezone.now() + timedelta(days=7))
                self.client.force_login(user)
                response = self.client.post(reverse("plataforma:institutional_organization_invite_accept", args=[token]),
                    {"action": "accept"}, HTTP_HOST="camppg.palaciomental.com.br")
                expected = "plataforma:institutional_management" if role in ("gestor", "proprietario") else "core:index"
                self.assertRedirects(response, reverse(expected), fetch_redirect_response=False)

    def test_old_organization_invite_cannot_reactivate_or_change_role(self):
        user = User.objects.create_user(username="suspenso", email="suspenso@example.com")
        affiliation = MembroOrganizacao.objects.create(organizacao=self.organization, usuario=user,
            papel="professor", status=MembroOrganizacao.STATUS_SUSPENSA)
        token = secrets.token_urlsafe(32)
        invite = ConviteOrganizacao.objects.create(organizacao=self.organization, convidado_por=self.user,
            email=user.email, papel="membro", hash_token=hashlib.sha256(token.encode()).hexdigest(),
            expira_em=timezone.now() + timedelta(days=7))
        self.client.force_login(user)
        response = self.client.post(reverse("plataforma:institutional_organization_invite_accept", args=[token]),
            {"action": "accept"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 403)
        affiliation.refresh_from_db()
        invite.refresh_from_db()
        self.assertEqual(affiliation.status, MembroOrganizacao.STATUS_SUSPENSA)
        self.assertEqual(affiliation.papel, "professor")
        self.assertEqual(invite.status, ConviteOrganizacao.STATUS_PENDENTE)

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
        self.assertContains(response, "Criar conta e continuar")
        self.assertFalse(MembroOrganizacao.objects.filter(usuario=invited).exists())

        self.client.force_login(invited)
        response = self.client.post(
            reverse("plataforma:institutional_invite_accept", kwargs={"token": raw_token}),
            {"action": "accept"},
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertRedirects(response, reverse("core:index"), fetch_redirect_response=False)
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

    def test_professor_cannot_invite_to_group_even_when_assigned(self):
        professor = User.objects.create_user(username="professor", email="professor@example.com", password="Senha-forte-123")
        target = User.objects.create_user(username="aluno", email="aluno@example.com", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=professor, papel=MembroOrganizacao.PAPEL_PROFESSOR)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa professores", slug="programa-professores", criado_por=professor)
        grupo = self.make_group(programa, "Grupo orientado", criado_por=professor, professor=professor)
        self.client.force_login(professor)
        response = self.client.post(reverse("plataforma:institutional_group_members", kwargs={"group_id": grupo.pk}), {"email": target.email, "papel": "membro"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ConviteGrupo.objects.filter(grupo=grupo, email=target.email).exists())

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
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa de e-mail", slug="programa-email", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        grupo = self.make_group(programa, "Grupo de convite")
        destinatario = User.objects.create_user(username="destinatario-grupo", email="email@example.com")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=destinatario, papel=MembroOrganizacao.PAPEL_MEMBRO)
        MembroTurma.objects.create(turma=grupo.turma, usuario=self.user)
        MembroTurma.objects.create(turma=grupo.turma, usuario=destinatario)
        MembroGrupo.objects.create(grupo=grupo, usuario=self.user, representante=True)
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("plataforma:institutional_group_members", kwargs={"group_id": grupo.pk}), {"email": "email@example.com", "papel": "membro"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to[0], "email@example.com")
        self.assertEqual(cast(EmailMultiAlternatives, mail.outbox[0]).alternatives[0][1], "text/html")
        self.assertIn("Grupo de convite", mail.outbox[0].body)
        self.assertIn("camppg.palaciomental.com.br", html_alternative(mail.outbox[0]))

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
        self.assertIn("Aceitar convite", html_alternative(mail.outbox[0]))

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
        response = self.client.post(
            reverse("plataforma:institutional_organization_invite_accept", kwargs={"token": raw_token}),
            {"action": "accept"},
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertRedirects(response, reverse("core:index"), fetch_redirect_response=False)
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
