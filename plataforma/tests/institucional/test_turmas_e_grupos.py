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
from plataforma.forms import ProjectBasicsForm


User = get_user_model()


from .base import PortalInstitucionalBase


class TurmasEGruposTests(PortalInstitucionalBase):
    def test_member_sees_published_programs_and_cannot_open_draft(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        publicado = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa público", slug="publico", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        rascunho = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa rascunho", slug="rascunho", criado_por=self.user)
        self.client.force_login(self.user)
        response = self.client.get(reverse("plataforma:institutional_programs"), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(response, publicado.nome)
        self.assertNotContains(response, rascunho.nome)
        self.assertEqual(self.client.get(reverse("plataforma:institutional_program_detail", args=[rascunho.pk]), HTTP_HOST="camppg.palaciomental.com.br").status_code, 404)

    def test_program_creation_has_its_own_manager_only_page(self):
        afiliacao = MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_GESTOR)
        self.client.force_login(self.user)
        lista = self.client.get(reverse("plataforma:institutional_programs"), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(lista, reverse("plataforma:institutional_program_create"))
        self.assertNotContains(lista, 'name="nome"')
        formulario = self.client.get(reverse("plataforma:institutional_program_create"), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(formulario, 'name="nome"')
        afiliacao.papel = MembroOrganizacao.PAPEL_MEMBRO
        afiliacao.save(update_fields=["papel"])
        self.assertEqual(self.client.get(reverse("plataforma:institutional_program_create"), HTTP_HOST="camppg.palaciomental.com.br").status_code, 403)

    def test_only_student_in_active_class_can_create_group(self):
        afiliacao = MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa", slug="programa-papeis", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma", criado_por=self.user)
        MembroTurma.objects.create(turma=turma, usuario=self.user)
        grupo_existente = Grupo.objects.create(turma=turma, nome="Grupo existente", criado_por=self.user, aberto_para_entrada=True)
        self.client.force_login(self.user)
        url = reverse("plataforma:institutional_group_create_for_class", args=[turma.pk])
        for papel in (MembroOrganizacao.PAPEL_PROFESSOR, MembroOrganizacao.PAPEL_GESTOR, MembroOrganizacao.PAPEL_PROPRIETARIO):
            afiliacao.papel = papel
            afiliacao.save(update_fields=["papel"])
            self.assertEqual(self.client.post(url, {"nome": "Indevido", "status": "ativo"}, HTTP_HOST="camppg.palaciomental.com.br").status_code, 403)
            self.assertEqual(self.client.post(reverse("plataforma:institutional_group_request_join", args=[grupo_existente.pk]), HTTP_HOST="camppg.palaciomental.com.br").status_code, 403)
        afiliacao.papel = MembroOrganizacao.PAPEL_MEMBRO
        afiliacao.save(update_fields=["papel"])
        self.assertEqual(self.client.post(url, {"nome": "Grupo aluno", "status": "ativo"}, HTTP_HOST="camppg.palaciomental.com.br").status_code, 302)
        self.assertTrue(MembroGrupo.objects.filter(grupo__nome="Grupo aluno", usuario=self.user, representante=True).exists())

    def test_deletion_is_manager_only_and_preserves_linked_projects(self):
        afiliacao = MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa", slug="programa-exclusao", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma", criado_por=self.user)
        grupo = Grupo.objects.create(turma=turma, nome="Grupo", criado_por=self.user)
        MembroGrupo.objects.create(grupo=grupo, usuario=self.user, representante=True)
        projeto = Project.objects.create(owner=self.user, organizacao=self.organization, title="Projeto", direction="Teste", category="Teste")
        vinculo = VinculoProjetoInstitucional.objects.create(projeto=projeto, turma=turma, grupo=grupo, vinculado_por=self.user)
        self.client.force_login(self.user)
        url = reverse("plataforma:institutional_program_delete", args=[programa.pk])
        self.assertEqual(self.client.post(url, HTTP_HOST="camppg.palaciomental.com.br").status_code, 403)
        afiliacao.papel = MembroOrganizacao.PAPEL_GESTOR
        afiliacao.save(update_fields=["papel"])
        self.assertContains(self.client.get(url, HTTP_HOST="camppg.palaciomental.com.br"), "Existem projetos vinculados")
        self.assertEqual(self.client.post(url, HTTP_HOST="camppg.palaciomental.com.br").status_code, 409)
        self.assertTrue(VinculoProjetoInstitucional.objects.filter(pk=vinculo.pk).exists())
        vinculo.delete()
        self.assertEqual(self.client.post(url, HTTP_HOST="camppg.palaciomental.com.br").status_code, 409)
        grupo_url = reverse("plataforma:institutional_group_delete", args=[grupo.pk])
        outro_gestor = User.objects.create_user(username="outro-gestor", email="outro-gestor@example.com")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=outro_gestor, papel=MembroOrganizacao.PAPEL_GESTOR)
        self.client.force_login(outro_gestor)
        self.assertEqual(self.client.post(grupo_url, HTTP_HOST="camppg.palaciomental.com.br").status_code, 403)
        self.client.force_login(self.user)
        afiliacao.papel = MembroOrganizacao.PAPEL_MEMBRO
        afiliacao.save(update_fields=["papel"])
        self.assertEqual(self.client.post(grupo_url, HTTP_HOST="camppg.palaciomental.com.br").status_code, 302)
        afiliacao.papel = MembroOrganizacao.PAPEL_GESTOR
        afiliacao.save(update_fields=["papel"])
        turma_url = reverse("plataforma:institutional_class_delete", args=[turma.pk])
        self.assertEqual(self.client.post(turma_url, HTTP_HOST="camppg.palaciomental.com.br").status_code, 302)
        self.assertEqual(self.client.post(url, HTTP_HOST="camppg.palaciomental.com.br").status_code, 302)
        self.assertFalse(ProgramaInstitucional.objects.filter(pk=programa.pk).exists())
        self.assertTrue(Project.objects.filter(pk=projeto.pk).exists())

    def test_student_project_form_only_lists_groups_the_student_joins(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa", slug="programa-projeto", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma", criado_por=self.user)
        MembroTurma.objects.create(turma=turma, usuario=self.user)
        meu_grupo = Grupo.objects.create(turma=turma, nome="Meu grupo", criado_por=self.user)
        outro_grupo = Grupo.objects.create(turma=turma, nome="Outro grupo", criado_por=self.user)
        MembroGrupo.objects.create(grupo=meu_grupo, usuario=self.user)
        form = ProjectBasicsForm(owner=self.user, organizacao=self.organization)
        self.assertIn(meu_grupo, form.fields["grupo"].queryset)
        self.assertNotIn(outro_grupo, form.fields["grupo"].queryset)

    def test_representative_can_invite_only_active_students_in_same_class(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        outro = User.objects.create_user(username="fora-da-turma", email="fora@example.com")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=outro, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa", slug="programa-convite-grupo", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma", criado_por=self.user)
        MembroTurma.objects.create(turma=turma, usuario=self.user)
        grupo = Grupo.objects.create(turma=turma, nome="Grupo", criado_por=self.user)
        MembroGrupo.objects.create(grupo=grupo, usuario=self.user, representante=True)
        self.client.force_login(self.user)
        url = reverse("plataforma:institutional_group_members", args=[grupo.pk])
        response = self.client.post(url, {"email": outro.email}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(response, "Você pode convidar apenas alunos ativos desta turma.")
        self.assertFalse(ConviteGrupo.objects.filter(grupo=grupo).exists())
        MembroTurma.objects.create(turma=turma, usuario=outro)
        self.assertEqual(self.client.post(url, {"email": outro.email}, HTTP_HOST="camppg.palaciomental.com.br").status_code, 302)
        self.assertTrue(ConviteGrupo.objects.filter(grupo=grupo, email=outro.email).exists())
        editar = reverse("plataforma:institutional_group_edit", args=[grupo.pk])
        self.assertEqual(self.client.post(editar, {"nome": "Grupo atualizado", "status": "ativo"}, HTTP_HOST="camppg.palaciomental.com.br").status_code, 302)
        grupo.refresh_from_db()
        self.assertEqual(grupo.nome, "Grupo atualizado")
        self.client.force_login(outro)
        self.assertEqual(self.client.post(editar, {"nome": "Indevido", "status": "ativo"}, HTTP_HOST="camppg.palaciomental.com.br").status_code, 403)

    def test_only_group_members_invite_and_only_author_deletes_group(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        colega = User.objects.create_user(username="colega", email="colega@example.com")
        alvo = User.objects.create_user(username="aluno-alvo", email="alvo@example.com")
        gestor = User.objects.create_user(username="gestor-grupo", email="gestor@example.com")
        for usuario, papel in [(colega, MembroOrganizacao.PAPEL_MEMBRO), (alvo, MembroOrganizacao.PAPEL_MEMBRO), (gestor, MembroOrganizacao.PAPEL_GESTOR)]:
            MembroOrganizacao.objects.create(organizacao=self.organization, usuario=usuario, papel=papel)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa", slug="grupo-autonomia", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma", criado_por=self.user)
        for usuario in (self.user, colega, alvo):
            MembroTurma.objects.create(turma=turma, usuario=usuario)
        grupo = Grupo.objects.create(turma=turma, nome="Grupo autônomo", criado_por=self.user)
        MembroGrupo.objects.create(grupo=grupo, usuario=self.user, representante=True)
        MembroGrupo.objects.create(grupo=grupo, usuario=colega)
        grupo_url = reverse("plataforma:institutional_group_members", args=[grupo.pk])
        excluir = reverse("plataforma:institutional_group_delete", args=[grupo.pk])
        self.client.force_login(gestor)
        self.assertEqual(self.client.post(grupo_url, {"email": alvo.email}, HTTP_HOST="camppg.palaciomental.com.br").status_code, 403)
        self.assertEqual(self.client.post(excluir, HTTP_HOST="camppg.palaciomental.com.br").status_code, 403)
        self.client.force_login(colega)
        self.assertEqual(self.client.post(excluir, HTTP_HOST="camppg.palaciomental.com.br").status_code, 403)
        self.assertEqual(self.client.post(grupo_url, {"email": alvo.email}, HTTP_HOST="camppg.palaciomental.com.br").status_code, 302)
        self.assertTrue(ConviteGrupo.objects.filter(grupo=grupo, email=alvo.email).exists())
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(excluir, HTTP_HOST="camppg.palaciomental.com.br").status_code, 302)

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
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa aberto", slug="programa-aberto", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma aberta", criado_por=self.user, politica_participacao=Turma.POLITICA_ABERTA)
        self.client.force_login(self.user)
        response = self.client.post(reverse("plataforma:institutional_class_participate", kwargs={"turma_id": turma.pk}), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MembroTurma.objects.filter(turma=turma, usuario=self.user, status=MembroTurma.STATUS_ATIVO).exists())

    def test_approval_class_creates_request_and_professor_can_approve(self):
        professor = User.objects.create_user(username="professor-aprovador", email="professor-aprovador@example.com", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=professor, papel=MembroOrganizacao.PAPEL_PROFESSOR)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa aprovação", slug="programa-aprovacao", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=professor)
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
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa de grupos", slug="programa-de-grupos", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
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
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa grupo aberto", slug="programa-grupo-aberto", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
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
        self.client.force_login(target)
        profile = self.client.get(reverse("plataforma:institutional_profile") + "?aba=colaboracoes", HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(profile, "Grupo aberto")
        self.assertContains(profile, reverse("plataforma:institutional_group_members", args=[grupo.pk]))
        membership = MembroGrupo.objects.get(grupo=grupo, usuario=target)
        membership.status = MembroGrupo.STATUS_SUSPENSO
        membership.save(update_fields=["status"])
        profile = self.client.get(reverse("plataforma:institutional_profile") + "?aba=colaboracoes", HTTP_HOST="camppg.palaciomental.com.br")
        self.assertNotContains(profile, "Grupo aberto")

    def test_member_can_only_create_one_group_per_class_until_leaving(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa grupo único", slug="programa-grupo-unico", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma grupo único", criado_por=self.user, politica_participacao=Turma.POLITICA_ABERTA)
        MembroTurma.objects.create(turma=turma, usuario=self.user)
        self.client.force_login(self.user)
        url = reverse("plataforma:institutional_group_create_for_class", kwargs={"turma_id": turma.pk})
        self.assertEqual(self.client.post(url, {"nome": "Primeiro grupo", "status": Grupo.STATUS_ATIVO}, HTTP_HOST="camppg.palaciomental.com.br").status_code, 302)
        bloqueado = self.client.post(url, {"nome": "Segundo grupo", "status": Grupo.STATUS_ATIVO}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(bloqueado, "já participa de um grupo nesta turma")
        grupo = Grupo.objects.get(nome="Primeiro grupo")
        self.assertEqual(self.client.post(reverse("plataforma:institutional_group_leave", kwargs={"group_id": grupo.pk}), HTTP_HOST="camppg.palaciomental.com.br").status_code, 302)
        self.assertEqual(self.client.post(url, {"nome": "Segundo grupo", "status": Grupo.STATUS_ATIVO}, HTTP_HOST="camppg.palaciomental.com.br").status_code, 302)

    def test_class_member_can_preview_group_without_seeing_private_members(self):
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO)
        colega = User.objects.create_user(username="colega-preview", email="colega-preview@example.com")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=colega, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa preview", slug="programa-preview", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma preview", criado_por=self.user, politica_participacao=Turma.POLITICA_ABERTA)
        MembroTurma.objects.create(turma=turma, usuario=self.user)
        MembroTurma.objects.create(turma=turma, usuario=colega)
        grupo = Grupo.objects.create(turma=turma, nome="Grupo preview", criado_por=colega, descricao="Objetivo de preview")
        MembroGrupo.objects.create(grupo=grupo, usuario=colega, representante=True)
        self.client.force_login(self.user)
        response = self.client.get(reverse("plataforma:institutional_group_members", kwargs={"group_id": grupo.pk}), HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(response, "Preview do grupo")
        self.assertContains(response, "Objetivo de preview")
        self.assertNotContains(response, "@colega-preview")

    def test_group_invite_accepts_username_as_primary_target(self):
        target = User.objects.create_user(username="aluno-por-usuario", email="aluno-por-usuario@example.com")
        for usuario in (self.user, target):
            MembroOrganizacao.objects.create(organizacao=self.organization, usuario=usuario, papel=MembroOrganizacao.PAPEL_MEMBRO)
        programa = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa @", slug="programa-arroba", status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user)
        turma = Turma.objects.create(programa=programa, nome="Turma @", criado_por=self.user)
        for usuario in (self.user, target):
            MembroTurma.objects.create(turma=turma, usuario=usuario)
        grupo = Grupo.objects.create(turma=turma, nome="Grupo @", criado_por=self.user)
        MembroGrupo.objects.create(grupo=grupo, usuario=self.user, representante=True)
        self.client.force_login(self.user)
        response = self.client.post(reverse("plataforma:institutional_group_members", kwargs={"group_id": grupo.pk}), {"email": "@aluno-por-usuario"}, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ConviteGrupo.objects.filter(grupo=grupo, email=target.email).exists())

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
