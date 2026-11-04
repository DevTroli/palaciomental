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


class TurmasEGruposTests(PortalInstitucionalBase):
    def test_program_class_group_hierarchy_keeps_members_in_scope(self):
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Iniciativa",
            slug="iniciativa",
            criado_por=self.user,
        )
        turma = Turma.objects.create(programa=programa, nome="Turma 2026", criado_por=self.user)
        grupo = Grupo.objects.create(
            turma=turma,
            nome="Grupo A",
            criado_por=self.user,
            aberto_para_entrada=True,
        )
        MembroTurma.objects.create(turma=turma, usuario=self.user)
        MembroGrupo.objects.create(grupo=grupo, usuario=self.user, representante=True)

        self.assertEqual(grupo.turma.programa.organizacao_id, self.organization.pk)
        self.assertTrue(grupo.aberto_para_entrada)
        self.assertTrue(grupo.membros.filter(usuario=self.user, representante=True).exists())

    def test_institutional_project_link_rejects_group_from_another_class(self):
        programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Iniciativa",
            slug="iniciativa-incompatibilidade",
            criado_por=self.user,
        )
        turma_a = Turma.objects.create(programa=programa, nome="Turma A", criado_por=self.user)
        turma_b = Turma.objects.create(programa=programa, nome="Turma B", criado_por=self.user)
        grupo = Grupo.objects.create(turma=turma_a, nome="Grupo A", criado_por=self.user)
        projeto = Project.objects.create(
            owner=self.user,
            organizacao=self.organization,
            title="Projeto incompatível",
            direction="Teste",
            category="Teste",
        )
        vinculo = VinculoProjetoInstitucional(
            projeto=projeto,
            turma=turma_b,
            grupo=grupo,
            vinculado_por=self.user,
        )
        with self.assertRaises(ValidationError):
            vinculo.full_clean()

    def test_affiliated_member_can_enter_open_class(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa aberto", slug="programa-aberto", criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma aberta", criado_por=self.user, politica_participacao=Turma.POLITICA_ABERTA)
        self.client.force_login(self.user)
        response = self.client.post(reverse("plataforma:institutional_class_participate", kwargs={"turma_id": turma.pk}), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MembroTurma.objects.filter(turma=turma, usuario=self.user, status=MembroTurma.STATUS_ATIVO).exists())

    def test_approval_class_creates_request_and_professor_can_approve(self):
        professor = User.objects.create_user(username="professor-aprovador", email="professor-aprovador@example.com", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=professor, papel=MembroOrganizacao.PAPEL_PROFESSOR)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa aprovação", slug="programa-aprovacao", criado_por=professor)
        turma = Turma.objects.create(programa=programa, nome="Turma aprovação", criado_por=professor, professor_responsavel=professor, politica_participacao=Turma.POLITICA_APROVACAO)
        self.client.force_login(self.user)
        response = self.client.post(reverse("plataforma:institutional_class_participate", kwargs={"turma_id": turma.pk}), {"mensagem": "Quero participar."}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        solicitacao = SolicitacaoTurma.objects.get(turma=turma, usuario=self.user)
        self.client.force_login(professor)
        response = self.client.post(reverse("plataforma:institutional_class_request_decide", kwargs={"request_id": solicitacao.pk}), {"acao": "aprovar"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MembroTurma.objects.filter(turma=turma, usuario=self.user).exists())
        solicitacao.refresh_from_db()
        self.assertEqual(solicitacao.status, SolicitacaoTurma.STATUS_APROVADA)

    def test_closed_or_invite_only_class_rejects_direct_entry(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa protegido", slug="programa-protegido", criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma fechada", criado_por=self.user, politica_participacao=Turma.POLITICA_ENCERRADA, status=Turma.STATUS_ENCERRADO)
        self.client.force_login(self.user)
        response = self.client.post(reverse("plataforma:institutional_class_participate", kwargs={"turma_id": turma.pk}), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(MembroTurma.objects.filter(turma=turma, usuario=self.user).exists())

    def test_member_can_create_group_only_in_permitted_class(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa de grupos", slug="programa-de-grupos", criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma de grupos", criado_por=self.user, politica_participacao=Turma.POLITICA_ABERTA)
        MembroTurma.objects.create(turma=turma, usuario=self.user)
        self.client.force_login(self.user)
        response = self.client.post(reverse("plataforma:institutional_group_create_for_class", kwargs={"turma_id": turma.pk}), {"nome": "Grupo criado pelo aluno", "descricao": "", "status": Grupo.STATUS_ATIVO, "aberto_para_entrada": "on"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        grupo = Grupo.objects.get(turma=turma, nome="Grupo criado pelo aluno")
        self.assertTrue(MembroGrupo.objects.filter(grupo=grupo, usuario=self.user, representante=True).exists())

    def test_open_group_creates_request_and_representative_can_approve(self):
        target = User.objects.create_user(username="interessado", email="interessado@example.com", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=target, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa grupo aberto", slug="programa-grupo-aberto", criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma grupo aberto", criado_por=self.user, politica_participacao=Turma.POLITICA_ABERTA)
        MembroTurma.objects.create(turma=turma, usuario=self.user)
        MembroTurma.objects.create(turma=turma, usuario=target)
        grupo = Grupo.objects.create(turma=turma, nome="Grupo aberto", criado_por=self.user, aberto_para_entrada=True)
        MembroGrupo.objects.create(grupo=grupo, usuario=self.user, representante=True)
        self.client.force_login(target)
        response = self.client.post(reverse("plataforma:institutional_group_request_join", kwargs={"group_id": grupo.pk}), {"mensagem": "Posso ajudar."}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        solicitacao = SolicitacaoGrupo.objects.get(grupo=grupo, usuario=target)
        self.client.force_login(self.user)
        response = self.client.post(reverse("plataforma:institutional_group_request_decide", kwargs={"request_id": solicitacao.pk}), {"acao": "aprovar"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MembroGrupo.objects.filter(grupo=grupo, usuario=target).exists())

    def test_ineligible_member_does_not_see_invite_only_class(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa restrito", slug="programa-restrito", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        Turma.objects.create(programa=programa, nome="Turma por convite", criado_por=self.user, politica_participacao=Turma.POLITICA_CONVITE)
        self.client.force_login(self.user)
        response = self.client.get(reverse("plataforma:institutional_program_detail", kwargs={"programa_id": programa.pk}), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Turma por convite")

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
            reverse("plataforma:institutional_class_create", kwargs={"programa_id": programa.pk}),
            {"nome": "Turma 2026", "descricao": "Turma inicial.", "politica_participacao": Turma.POLITICA_CONVITE, "status": "ativo"},
            HTTP_HOST="camppg.palaciomental.com.br",
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Turma.objects.filter(programa=programa, nome="Turma 2026").exists())

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
