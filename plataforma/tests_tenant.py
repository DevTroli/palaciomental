import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import ConviteTurmaGrupo, DominioOrganizacao, MembroOrganizacao, MembroTurmaGrupo, Organizacao, ProgramaInstitucional, Project, TurmaGrupo


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
            f"{reverse('plataforma:login')}?next=/",
            fetch_redirect_response=False,
        )

    def test_tenant_auth_page_is_available_before_affiliation(self):
        response = self.client.get(
            reverse("plataforma:login"),
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

        self.assertRedirects(response, reverse("plataforma:institutional_management"), fetch_redirect_response=False)

    def test_manager_can_enter_institutional_management_portal(self):
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_GESTOR,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("plataforma:institutional_management"),
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Espaço de gestão")
        self.assertContains(response, "CAMPPG")
        self.assertContains(response, "Programas, turmas e grupos")

    def test_regular_member_cannot_enter_institutional_management_portal(self):
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("plataforma:institutional_management"),
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 403)

    def test_manager_can_create_program_and_group_in_current_tenant(self):
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_GESTOR,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("plataforma:institutional_programs"),
            {"nome": "Programa de Inovação", "descricao": "Projetos acompanhados.", "status": "rascunho"},
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 302)
        programa = ProgramaInstitucional.objects.get(organizacao=self.organization)
        self.assertEqual(programa.criado_por_id, self.user.pk)

        response = self.client.post(
            reverse("plataforma:institutional_group_create", kwargs={"programa_id": programa.pk}),
            {"nome": "Turma 2026", "tipo": "turma", "descricao": "Grupo inicial.", "status": "ativo"},
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(TurmaGrupo.objects.filter(programa=programa, nome="Turma 2026").exists())

    def test_regular_member_cannot_create_program(self):
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("plataforma:institutional_programs"),
            {"nome": "Programa indevido", "descricao": "", "status": "rascunho"},
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ProgramaInstitucional.objects.filter(nome="Programa indevido").exists())

    def test_program_detail_cannot_cross_tenant_boundary(self):
        outro = Organizacao.objects.create(slug="outra", nome="Outra organização")
        ProgramaInstitucional.objects.create(
            organizacao=outro,
            nome="Programa privado",
            slug="programa-privado",
            criado_por=self.user,
        )
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_GESTOR,
        )
        self.client.force_login(self.user)
        programa = ProgramaInstitucional.objects.get(organizacao=outro)

        response = self.client.get(
            reverse("plataforma:institutional_program_detail", kwargs={"programa_id": programa.pk}),
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 404)

    def test_unknown_subdomain_does_not_fall_back_to_another_tenant(self):
        response = self.client.get("/", HTTP_HOST="outra.palaciomental.com.br")

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "CAMPPG", status_code=404)

    def test_project_created_inside_tenant_is_institutional(self):
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("plataforma:project_create"),
            {
                "title": "Projeto CAMPPG",
                "direction": "Organizar uma iniciativa institucional.",
                "status": "ideia",
                "visibility": "privado",
            },
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(title="Projeto CAMPPG")
        self.assertEqual(project.organizacao_id, self.organization.pk)

    def test_personal_project_is_not_visible_from_an_institutional_host(self):
        personal = Project.objects.create(
            owner=self.user,
            title="Projeto pessoal",
            direction="Direção pessoal",
            category="Pesquisa",
        )
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("plataforma:project_detail", kwargs={"pk": personal.pk}),
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 404)

    def test_institutional_project_is_not_visible_from_global_space(self):
        project = Project.objects.create(
            owner=self.user,
            organizacao=self.organization,
            title="Projeto institucional",
            direction="Direção institucional",
            category="Educação",
        )

        response = self.client.get(
            reverse("plataforma:project_detail", kwargs={"pk": project.pk}),
            HTTP_HOST="palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 404)

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
        grupo = TurmaGrupo.objects.create(programa=programa, nome="Turma 2026", criado_por=manager)
        invited = User.objects.create_user(username="convidado", email="convidado@example.com", password="Senha-forte-123")
        raw_token = secrets.token_urlsafe(24)
        invite = ConviteTurmaGrupo.objects.create(
            turma_grupo=grupo,
            convidado_por=manager,
            email=invited.email,
            papel=MembroTurmaGrupo.PAPEL_MEMBRO,
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
        self.assertTrue(MembroTurmaGrupo.objects.filter(turma_grupo=grupo, usuario=invited, status=MembroTurmaGrupo.STATUS_ATIVO).exists())
        invite.refresh_from_db()
        self.assertEqual(invite.status, ConviteTurmaGrupo.STATUS_ACEITO)

    def test_expired_group_invitation_is_rejected(self):
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa expirado",
            slug="programa-expirado",
            criado_por=self.user,
        )
        grupo = TurmaGrupo.objects.create(programa=programa, nome="Grupo expirado", criado_por=self.user)
        raw_token = secrets.token_urlsafe(24)
        ConviteTurmaGrupo.objects.create(
            turma_grupo=grupo,
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
