import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import ConviteTurmaGrupo, DominioOrganizacao, MembroOrganizacao, MembroTurmaGrupo, Organizacao, ProgramaInstitucional, Project, ProjetoTurmaGrupo, TurmaGrupo


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

    def test_tenant_creation_cannot_accept_a_forged_organization_and_can_link_group(self):
        outro = Organizacao.objects.create(slug="outra", nome="Outra organização")
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa CAMPPG",
            slug="programa-camppg",
            criado_por=self.user,
        )
        grupo = TurmaGrupo.objects.create(programa=programa, nome="Grupo principal", criado_por=self.user)
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("plataforma:project_create"),
            {
                "title": "Projeto vinculado",
                "direction": "Projeto interno da CAMPPG.",
                "status": "ideia",
                "visibility": "privado",
                "turma_grupo": str(grupo.pk),
                "organizacao": str(outro.pk),
            },
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(title="Projeto vinculado")
        self.assertEqual(project.organizacao_id, self.organization.pk)
        self.assertTrue(ProjetoTurmaGrupo.objects.filter(projeto=project, turma_grupo=grupo).exists())

    def test_global_catalog_and_tenant_catalog_do_not_mix_projects(self):
        global_project = Project.objects.create(owner=self.user, title="Projeto global", direction="Referência pública", category="Pesquisa", visibility=Project.VISIBILITY_PUBLIC)
        tenant_project = Project.objects.create(owner=self.user, organizacao=self.organization, title="Projeto CAMPPG público", direction="Catálogo interno", category="Educação", visibility=Project.VISIBILITY_PUBLIC)
        outro = Organizacao.objects.create(slug="outra", nome="Outra organização")
        other_project = Project.objects.create(owner=self.user, organizacao=outro, title="Projeto de outra organização", direction="Não deve aparecer", category="Pesquisa", visibility=Project.VISIBILITY_PUBLIC)
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        self.client.force_login(self.user)

        global_response = self.client.get(reverse("plataforma:projects"), HTTP_HOST="palaciomental.com.br")
        self.assertContains(global_response, global_project.title)
        self.assertNotContains(global_response, tenant_project.title)
        self.assertNotContains(global_response, other_project.title)

        tenant_response = self.client.get(reverse("plataforma:projects"), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(tenant_response, tenant_project.title)
        self.assertNotContains(tenant_response, global_project.title)
        self.assertNotContains(tenant_response, other_project.title)
        self.assertContains(tenant_response, "Projetos da CAMPPG")

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
        grupo = TurmaGrupo.objects.create(programa=programa, nome="Grupo orientado", professor_responsavel=professor, criado_por=professor)
        self.client.force_login(professor)
        response = self.client.post(reverse("plataforma:institutional_group_members", kwargs={"group_id": grupo.pk}), {"email": target.email, "papel": MembroTurmaGrupo.PAPEL_MEMBRO}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ConviteTurmaGrupo.objects.filter(turma_grupo=grupo, email=target.email).exists())

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
        grupo = TurmaGrupo.objects.create(programa=programa, nome="Grupo de convite", criado_por=self.user)
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("plataforma:institutional_group_members", kwargs={"group_id": grupo.pk}), {"email": "email@example.com", "papel": MembroTurmaGrupo.PAPEL_MEMBRO}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to[0], "email@example.com")
        self.assertEqual(mail.outbox[0].alternatives[0][1], "text/html")
        self.assertIn("Grupo de convite", mail.outbox[0].body)
        self.assertIn("camppg.palaciomental.com.br", mail.outbox[0].alternatives[0][0])
