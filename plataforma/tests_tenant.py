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

from .models import ConviteOrganizacao, ConviteTurmaGrupo, DominioOrganizacao, IdentidadeOrganizacao, MembroOrganizacao, MembroTurmaGrupo, Organizacao, ProgramaInstitucional, Project, ProjetoTurmaGrupo, TurmaGrupo
from .services import ativar_organizacao


User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=["testserver", ".palaciomental.com.br", ".app.github.dev"],
    PALACIO_BASE_DOMAIN="palaciomental.com.br",
    TENANT_RESERVED_HOSTS=["www", "api", "status", "admin", "app"],
)
class TenantResolutionTests(TestCase):
    def setUp(self):
        self.organization = Organizacao.objects.create(slug="camppg", nome="CAMPPG", status=Organizacao.STATUS_ATIVA)
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
        self.pm_staff = User.objects.create_user(
            username="pm-staff",
            email="pm-staff@example.com",
            password="Senha-forte-123",
            is_staff=True,
        )

    def logo_file(self, name="logo.png", size=(320, 120), image_format="PNG"):
        buffer = BytesIO()
        Image.new("RGBA", size, (110, 74, 163, 255)).save(buffer, format=image_format)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")

    def test_logo_is_validated_and_saved_under_tenant_path(self):
        identidade = IdentidadeOrganizacao.objects.create(
            organizacao=self.organization,
            logo=self.logo_file(),
            cor_primaria="roxo-institucional",
            cor_destaque="verde-institucional",
            cor_fundo="bege-claro",
        )
        self.assertTrue(identidade.completa)
        self.assertIn(f"tenants/{self.organization.pk}/branding/logo/", identidade.logo.name)

    def test_invalid_logo_format_is_rejected(self):
        identidade = IdentidadeOrganizacao(
            organizacao=self.organization,
            logo=SimpleUploadedFile("logo.gif", b"not-an-image", content_type="image/gif"),
        )
        with self.assertRaises(ValidationError):
            identidade.full_clean()

    def test_logo_over_two_megabytes_is_rejected(self):
        identidade = IdentidadeOrganizacao(
            organizacao=self.organization,
            logo=SimpleUploadedFile("logo.png", b"x" * (2 * 1024 * 1024 + 1), content_type="image/png"),
        )
        with self.assertRaisesMessage(ValidationError, "no máximo 2 MB"):
            identidade.full_clean()

    def test_organization_activation_requires_identity_domain_and_owner(self):
        self.organization.status = Organizacao.STATUS_CONFIGURANDO
        self.organization.save(update_fields=["status"])
        with self.assertRaisesMessage(Exception, "Configure a logo"):
            ativar_organizacao(self.organization, executor=self.pm_staff)

        IdentidadeOrganizacao.objects.create(
            organizacao=self.organization,
            logo=self.logo_file(),
            cor_primaria="roxo-institucional",
            cor_destaque="verde-institucional",
            cor_fundo="bege-claro",
        )
        DominioOrganizacao.objects.filter(organizacao=self.organization).delete()
        with self.assertRaisesMessage(Exception, "domínio principal"):
            ativar_organizacao(self.organization, executor=self.pm_staff)

        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_PROPRIETARIO,
        )
        DominioOrganizacao.objects.create(
            organizacao=self.organization,
            hostname="camppg.palaciomental.com.br",
            principal=True,
            status_verificacao="ativo",
        )
        with self.assertRaisesMessage(Exception, "Somente a equipe"):
            ativar_organizacao(self.organization, executor=self.user)
        self.assertEqual(self.organization.status, Organizacao.STATUS_CONFIGURANDO)

    def test_configured_organization_can_be_activated_by_staff(self):
        self.organization.status = Organizacao.STATUS_CONFIGURANDO
        self.organization.save(update_fields=["status"])
        IdentidadeOrganizacao.objects.create(
            organizacao=self.organization,
            logo=self.logo_file(),
            cor_primaria="roxo-institucional",
            cor_destaque="verde-institucional",
            cor_fundo="bege-claro",
        )
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_PROPRIETARIO,
        )
        ativar_organizacao(self.organization, executor=self.pm_staff)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.status, Organizacao.STATUS_ATIVA)

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
        self.assertContains(response, "Ambiente institucional privado")
        self.assertNotContains(response, "Cadastre-se")
        self.assertContains(response, "Voltar ao início do Palácio Mental")

    @override_settings(DEBUG=True)
    def test_restricted_access_returns_to_global_host_in_codespace(self):
        self.client.force_login(self.user)
        response = self.client.get("/?tenant=camppg", HTTP_HOST="codespace-8000.app.github.dev")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "http://codespace-8000.app.github.dev/", status_code=403)

    def test_tenant_registration_is_closed_and_contextualized(self):
        response = self.client.get(
            reverse("plataforma:register"),
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Cadastro fechado", status_code=403)
        self.assertContains(response, "somente por convite", status_code=403)

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
        self.assertContains(response, "Ambiente institucional")
        self.assertContains(response, "Programas ativos")

    def test_tenant_home_shows_only_published_current_tenant_content(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa CAMPPG",
            slug="programa-camppg-home",
            status=ProgramaInstitucional.STATUS_PUBLICADO,
            criado_por=self.user,
        )
        TurmaGrupo.objects.create(programa=programa, nome="Grupo CAMPPG", criado_por=self.user)
        Project.objects.create(
            owner=self.user,
            organizacao=self.organization,
            title="Projeto CAMPPG publicado",
            direction="Projeto dentro do tenant",
            category="Educação",
            visibility=Project.VISIBILITY_PUBLIC,
        )
        other = Organizacao.objects.create(slug="outra", nome="Outra organização", status=Organizacao.STATUS_ATIVA)
        Project.objects.create(
            owner=self.user,
            organizacao=other,
            title="Projeto de outro tenant",
            direction="Não deve aparecer",
            category="Outro",
            visibility=Project.VISIBILITY_PUBLIC,
        )
        self.client.force_login(self.user)
        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Programa CAMPPG")
        self.assertContains(response, "Projeto CAMPPG publicado")
        self.assertNotContains(response, "Projeto de outro tenant")

    def test_member_home_limits_turmas_to_their_active_group_scope(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa de grupos",
            slug="programa-grupos-home",
            status=ProgramaInstitucional.STATUS_PUBLICADO,
            criado_por=self.user,
        )
        own_group = TurmaGrupo.objects.create(programa=programa, nome="Grupo do participante", criado_por=self.user)
        other_group = TurmaGrupo.objects.create(programa=programa, nome="Grupo de outra equipe", criado_por=self.user)
        MembroTurmaGrupo.objects.create(turma_grupo=own_group, usuario=self.user)
        self.client.force_login(self.user)
        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(response, "Grupo do participante")
        self.assertNotContains(response, "Grupo de outra equipe")

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
        self.assertContains(response, "Membros ativos")
        self.assertNotContains(response, "Responsabilidade do proprietário")

    def test_login_redirects_manager_to_management_and_member_to_tenant_home(self):
        manager = User.objects.create_user(username="login-gestor", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=manager, papel=MembroOrganizacao.PAPEL_GESTOR)
        response = self.client.post(
            reverse("plataforma:login"),
            {"username": "login-gestor", "password": "Senha-forte-123"},
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertRedirects(response, reverse("plataforma:institutional_management"), fetch_redirect_response=False)

        self.client.logout()
        member = User.objects.create_user(username="login-membro", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=member, papel=MembroOrganizacao.PAPEL_MEMBRO)
        response = self.client.post(
            reverse("plataforma:login"),
            {"username": "login-membro", "password": "Senha-forte-123"},
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertRedirects(response, reverse("core:index"), fetch_redirect_response=False)

    def test_owner_dashboard_shows_owner_governance_action_and_tenant_metrics(self):
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_PROPRIETARIO,
        )
        ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa no painel",
            slug="programa-no-painel",
            status=ProgramaInstitucional.STATUS_PUBLICADO,
            criado_por=self.user,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("plataforma:institutional_management"),
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Responsabilidade do proprietário")
        self.assertContains(response, "Programas publicados")
        self.assertContains(response, "1", html=False)

    def test_manager_can_update_tenant_identity_from_portal(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_GESTOR)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("plataforma:institutional_identity"),
            {"nome_exibicao": "CAMPPG Projetos", "cor_primaria": "azul-sobrio", "cor_destaque": "verde-institucional", "cor_fundo": "bege-claro"},
            HTTP_HOST="camppg.palaciomental.com.br",
        )
        self.assertRedirects(response, reverse("plataforma:institutional_identity"), fetch_redirect_response=False)
        identidade = IdentidadeOrganizacao.objects.get(organizacao=self.organization)
        self.assertEqual(identidade.nome_exibicao, "CAMPPG Projetos")
        self.assertEqual(identidade.cor_primaria, "azul-sobrio")

    def test_regular_member_cannot_update_tenant_identity(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        self.client.force_login(self.user)
        response = self.client.get(reverse("plataforma:institutional_identity"), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 403)

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
