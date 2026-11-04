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


class ProjetosInstitucionaisTests(PortalInstitucionalBase):
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
                "tipo_projeto": "autonomo",
            },
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(title="Projeto CAMPPG")
        self.assertEqual(project.organizacao_id, self.organization.pk)
        self.assertFalse(VinculoProjetoInstitucional.objects.filter(projeto=project).exists())

    def test_program_project_requires_an_eligible_orienting_professor(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa obrigatório", slug="programa-obrigatorio", criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma orientada", criado_por=self.user)
        self.client.force_login(self.user)
        response = self.client.post(reverse("plataforma:project_create"), {"title": "Projeto sem orientador", "direction": "Teste", "status": "ideia", "visibility": "privado", "tipo_projeto": "programa", "turma": str(turma.pk)}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Project.objects.filter(title="Projeto sem orientador").exists())

    def test_individual_oriented_project_can_exist_without_group(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_PROFESSOR)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa individual", slug="programa-individual", criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma individual", criado_por=self.user, professor_responsavel=self.user)
        MembroTurma.objects.create(turma=turma, usuario=self.user)
        self.client.force_login(self.user)
        response = self.client.post(reverse("plataforma:project_create"), {"title": "Projeto individual orientado", "direction": "Pesquisa solo", "status": "ideia", "visibility": "privado", "tipo_projeto": "programa", "turma": str(turma.pk), "orientador": str(self.user.pk)}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(title="Projeto individual orientado")
        vinculo = VinculoProjetoInstitucional.objects.get(projeto=project)
        self.assertEqual(vinculo.turma_id, turma.pk)
        self.assertIsNone(vinculo.grupo_id)
        self.assertEqual(vinculo.orientador_id, self.user.pk)

    def test_editing_oriented_project_to_autonomous_removes_institutional_link(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_PROFESSOR)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa de transição", slug="programa-transicao", criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma de transição", criado_por=self.user, professor_responsavel=self.user)
        project = Project.objects.create(owner=self.user, organizacao=self.organization, title="Projeto para desvincular", direction="Contexto", category="Pesquisa")
        VinculoProjetoInstitucional.objects.create(projeto=project, turma=turma, orientador=self.user, vinculado_por=self.user)
        self.client.force_login(self.user)
        response = self.client.post(reverse("plataforma:project_edit", kwargs={"pk": project.pk}), {"title": project.title, "direction": project.direction, "status": project.status, "visibility": project.visibility, "tipo_projeto": "autonomo"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(VinculoProjetoInstitucional.objects.filter(projeto=project).exists())

    def test_tenant_creation_cannot_accept_a_forged_organization_and_can_link_group(self):
        outro = Organizacao.objects.create(slug="outra", nome="Outra organização")
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa CAMPPG",
            slug="programa-camppg",
            criado_por=self.user,
        )
        grupo = self.make_group(programa, "Grupo principal", professor=self.user)
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_PROFESSOR)
        MembroTurma.objects.create(turma=grupo.turma, usuario=self.user)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("plataforma:project_create"),
            {
                "title": "Projeto vinculado",
                "direction": "Projeto interno da CAMPPG.",
                "status": "ideia",
                "visibility": "privado",
                "tipo_projeto": "programa",
                "turma": str(grupo.turma.pk),
                "grupo": str(grupo.pk),
                "orientador": str(self.user.pk),
                "organizacao": str(outro.pk),
            },
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(title="Projeto vinculado")
        self.assertEqual(project.organizacao_id, self.organization.pk)
        self.assertTrue(VinculoProjetoInstitucional.objects.filter(projeto=project, grupo=grupo).exists())

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
