from typing import cast
from django.db.models.fields.files import ImageFieldFile

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


class AcessoAoTenantTests(PortalInstitucionalBase):
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
        self.assertContains(response, "Projetos da comunidade")
        self.assertEqual(response.context["organizacao"], self.organization)
        self.assertContains(response, "Ranking de projetos")

    def test_tenant_home_shows_only_published_current_tenant_content(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa CAMPPG",
            slug="programa-camppg-home",
            status=ProgramaInstitucional.STATUS_PUBLICADO,
            criado_por=self.user,
        )
        self.make_group(programa, "Grupo CAMPPG")
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
        self.assertNotContains(response, "Programa CAMPPG")
        self.assertContains(response, "Projeto CAMPPG publicado")

    def test_tenant_shell_has_skip_link_navigation_footer_and_no_global_vitrine_link(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        self.client.force_login(self.user)
        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pular para o conteúdo principal")
        self.assertContains(response, 'aria-label="Navegação do ambiente"')
        self.assertContains(response, "Meus Projetos")
        self.assertContains(response, 'href="http://palaciomental.com.br/" aria-label="Ir para a página inicial do Palácio Mental"')
        self.assertContains(response, "Dê continuidade às suas ideias.")
        footer = response.content.decode().split('<footer class="camp-footer', 1)[1].split('</footer>', 1)[0]
        self.assertNotIn("Início do ambiente", footer)
        self.assertNotIn("Meu espaço pessoal", footer)
        self.assertIn("Status do sistema", footer)
        self.assertContains(response, "tenant-footer")
        self.assertNotContains(response, "Vitrine global")
        self.assertNotContains(response, "Projeto de outro tenant")

    def test_member_home_keeps_group_content_on_its_dedicated_screen(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa de grupos",
            slug="programa-grupos-home",
            status=ProgramaInstitucional.STATUS_PUBLICADO,
            criado_por=self.user,
        )
        own_group = self.make_group(programa, "Grupo do participante")
        other_group = self.make_group(programa, "Grupo de outra equipe")
        MembroTurma.objects.create(turma=own_group.turma, usuario=self.user)
        MembroGrupo.objects.create(grupo=own_group, usuario=self.user)
        self.client.force_login(self.user)
        response = self.client.get("/", HTTP_HOST="camppg.palaciomental.com.br")
        self.assertNotContains(response, "Grupo do participante")
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

    def test_identity_editor_has_live_preview_and_shell_uses_uploaded_logo(self):
        identidade = IdentidadeOrganizacao.objects.create(
            organizacao=self.organization,
            nome_exibicao="CAMPPG com identidade",
            logo=self.logo_file("camp-logo.png"),
            cor_primaria="azul-sobrio",
            cor_destaque="verde-institucional",
            cor_fundo="bege-claro",
        )
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_GESTOR)
        self.client.force_login(self.user)
        response = self.client.get(reverse("plataforma:institutional_identity"), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pré-visualização")
        self.assertContains(response, "tenant-identity.js")
        self.assertContains(response, 'data-theme-color="primary"')
        self.assertContains(response, 'data-theme-color="surface"')
        self.assertContains(response, cast(ImageFieldFile, identidade.logo).url)

        programs_response = self.client.get(reverse("plataforma:institutional_programs"), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(programs_response, cast(ImageFieldFile, identidade.logo).url)

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
