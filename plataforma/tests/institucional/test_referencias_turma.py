from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone

from plataforma.models import (
    GuardiaoLinkPendente,
    MembroOrganizacao,
    MembroTurma,
    Notification,
    Organizacao,
    ProgramaInstitucional,
    ProjectLink,
    Turma,
)

from .base import PortalInstitucionalBase


class ReferenciasTurmaTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        self.professor = self.user
        self.professor_affiliation = MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.professor,
            papel=MembroOrganizacao.PAPEL_PROFESSOR,
        )
        self.programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Programa de leitura",
            slug="programa-leitura",
            status=ProgramaInstitucional.STATUS_PUBLICADO,
            criado_por=self.professor,
        )
        self.turma = Turma.objects.create(
            programa=self.programa,
            nome="Turma da manhã",
            professor_responsavel=self.professor,
            criado_por=self.professor,
        )
        self.url = reverse("plataforma:institutional_program_detail", args=[self.programa.pk])
        self.create_url = reverse("plataforma:institutional_class_reference_create", args=[self.turma.pk])
        self.client.force_login(self.professor)

    @patch("plataforma.guardiao_consulta.consultar_ameacas", return_value=["NO_MATCH"])
    def test_professor_adiciona_edita_e_remove_referencia_e_link_entra_na_fila(self, _consulta):
        response = self.client.post(self.create_url, {
            "label": "Guia de leitura",
            "url": "https://example.com/guia",
            "descricao": "Material para começar a pesquisa.",
        }, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertRedirects(response, f"{self.url}#turma-{self.turma.pk}", fetch_redirect_response=False)
        referencia = ProjectLink.objects.get(turma=self.turma)
        self.assertEqual(referencia.descricao, "Material para começar a pesquisa.")
        self.assertTrue(GuardiaoLinkPendente.objects.filter(pk=referencia.pk).exists())

        with patch("plataforma.guardiao_consulta.consultar_links", return_value={}):
            self.assertEqual(self.client.get(self.url, HTTP_HOST="camppg.palaciomental.com.br").status_code, 200)
        edit_url = reverse("plataforma:institutional_class_reference_edit", args=[self.turma.pk, referencia.pk])
        response = self.client.post(edit_url, {
            "label": "Guia atualizado",
            "url": referencia.url,
            "descricao": "Versão revisada.",
        }, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertRedirects(response, f"{self.url}#turma-{self.turma.pk}", fetch_redirect_response=False)
        referencia.refresh_from_db()
        self.assertEqual(referencia.label, "Guia atualizado")

        delete_url = reverse("plataforma:institutional_class_reference_delete", args=[self.turma.pk, referencia.pk])
        response = self.client.post(delete_url, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertRedirects(response, f"{self.url}#turma-{self.turma.pk}", fetch_redirect_response=False)
        self.assertFalse(ProjectLink.objects.filter(pk=referencia.pk).exists())

    @patch("plataforma.guardiao_consulta.consultar_ameacas", return_value=["THREAT"])
    def test_link_identificado_como_ameaca_nao_e_salvo(self, _consulta):
        response = self.client.post(self.create_url, {
            "label": "Link de risco",
            "url": "https://example.com/risk",
            "descricao": "",
        }, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(response, "não pode ser salvo")
        self.assertFalse(ProjectLink.objects.filter(turma=self.turma).exists())

    @patch("plataforma.guardiao_consulta.consultar_ameacas", return_value=["UNVERIFIED"])
    def test_indisponibilidade_permite_salvar_mas_a_interface_avisa(self, _consulta):
        with patch("plataforma.guardiao_consulta.consultar_links", return_value={}):
            response = self.client.post(self.create_url, {
                "label": "Fonte pendente",
                "url": "https://example.com/source",
                "descricao": "",
            }, HTTP_HOST="camppg.palaciomental.com.br", follow=True)
        self.assertContains(response, "não foi possível verificar sua segurança")
        self.assertTrue(ProjectLink.objects.filter(turma=self.turma).exists())

    def test_somente_professor_responsavel_edita_e_aluno_da_turma_consulta(self):
        referencia = ProjectLink.objects.create(
            project=None,
            turma=self.turma,
            label="Referência da turma",
            url="https://example.com/reference",
        )
        aluno = type(self.user).objects.create_user(username="aluno-turma", password="Senha-forte-123")
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=aluno,
            papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        MembroTurma.objects.create(turma=self.turma, usuario=aluno)
        self.client.force_login(aluno)
        with patch("plataforma.guardiao_consulta.consultar_links", return_value={}):
            response = self.client.get(self.url, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(response, "REFERÊNCIA DA TURMA")
        self.assertNotContains(response, "Adicionar fonte")
        edit_url = reverse("plataforma:institutional_class_reference_edit", args=[self.turma.pk, referencia.pk])
        self.assertEqual(self.client.get(edit_url, HTTP_HOST="camppg.palaciomental.com.br").status_code, 403)

        outro_programa = ProgramaInstitucional.objects.create(
            organizacao=self.organization,
            nome="Outro programa",
            slug="outro-programa",
            status=ProgramaInstitucional.STATUS_PUBLICADO,
            criado_por=self.professor,
        )
        outra_turma = Turma.objects.create(programa=outro_programa, nome="Outra turma", criado_por=self.professor)
        outra_referencia = ProjectLink.objects.create(
            project=None,
            turma=outra_turma,
            label="Privada para outra turma",
            url="https://example.org/private",
        )
        self.assertEqual(
            self.client.get(reverse("plataforma:institutional_program_detail", args=[outro_programa.pk]), HTTP_HOST="camppg.palaciomental.com.br").status_code,
            200,
        )
        with patch("plataforma.guardiao_consulta.consultar_links", return_value={}):
            response = self.client.get(self.url, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertNotContains(response, outra_referencia.label.upper())

    def test_gestao_consulta_sem_editar_e_membro_sem_vinculo_nao_acessa(self):
        referencia = ProjectLink.objects.create(
            project=None,
            turma=self.turma,
            label="Roteiro da turma",
            url="https://example.com/roteiro",
        )
        gestor = type(self.user).objects.create_user(username="gestor-leitura", password="Senha-forte-123")
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=gestor,
            papel=MembroOrganizacao.PAPEL_GESTOR,
        )
        self.client.force_login(gestor)
        with patch("plataforma.guardiao_consulta.consultar_links", return_value={}):
            page = self.client.get(self.url, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(page, referencia.label.upper())
        self.assertNotContains(page, "Adicionar fonte")
        self.assertLess(page.content.index(b"Grupos da turma"), page.content.index(b"Fontes e links de refer\xc3\xaancia"))

        membro_sem_turma = type(self.user).objects.create_user(username="membro-sem-turma", password="Senha-forte-123")
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=membro_sem_turma,
            papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        self.client.force_login(membro_sem_turma)
        page = self.client.get(self.url, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertNotContains(page, referencia.label.upper())

    def test_referencia_de_turma_de_outro_tenant_nao_pode_ser_editada(self):
        outra = Organizacao.objects.create(slug="outra", nome="Outra organização", status=Organizacao.STATUS_ATIVA)
        outro_programa = ProgramaInstitucional.objects.create(
            organizacao=outra,
            nome="Programa alheio",
            slug="programa-alheio",
            status=ProgramaInstitucional.STATUS_PUBLICADO,
            criado_por=self.professor,
        )
        outra_turma = Turma.objects.create(programa=outro_programa, nome="Turma alheia", criado_por=self.professor)
        referencia = ProjectLink.objects.create(
            project=None,
            turma=outra_turma,
            label="Referência alheia",
            url="https://example.org/other",
        )
        edit_url = reverse("plataforma:institutional_class_reference_edit", args=[outra_turma.pk, referencia.pk])
        self.assertEqual(self.client.get(edit_url, HTTP_HOST="camppg.palaciomental.com.br").status_code, 404)

    def test_nao_permite_mais_de_seis_fontes(self):
        for index in range(6):
            ProjectLink.objects.create(
                project=None,
                turma=self.turma,
                label=f"Fonte {index}",
                url=f"https://example.com/{index}",
            )
        with patch("plataforma.guardiao_consulta.consultar_ameacas", return_value=["NO_MATCH"]):
            response = self.client.post(self.create_url, {
                "label": "Sétima fonte",
                "url": "https://example.com/seven",
                "descricao": "",
            }, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertContains(response, "limite de seis")
        self.assertEqual(ProjectLink.objects.filter(turma=self.turma).count(), 6)

    def test_turma_apresenta_os_mesmos_estados_do_guardiao_dos_projetos(self):
        referencia = ProjectLink.objects.create(
            project=None,
            turma=self.turma,
            label="Material de consulta",
            url="https://example.com/material",
        )
        GuardiaoLinkPendente.objects.filter(pk=referencia.pk).delete()
        estados = (
            ("ACESSIVEL", "Disponível"),
            ("REDIRECIONADO", "Redireciona"),
            ("REQUER_LOGIN", "Requer acesso"),
            ("QUEBRADO", "Link quebrado"),
            ("SEM_RESPOSTA", "Sem resposta"),
        )
        for status, rotulo in estados:
            with self.subTest(status=status), patch("plataforma.guardiao_consulta.consultar_links", return_value={
                referencia.pk: {"status": status, "label": rotulo, "tone": "neutral", "checked_at": timezone.now()},
            }):
                response = self.client.get(self.url, HTTP_HOST="camppg.palaciomental.com.br")
                self.assertContains(response, rotulo)
                self.assertContains(response, "Segurança não verificada")

    def test_url_invalida_nao_e_salva(self):
        response = self.client.post(self.create_url, {
            "label": "Fonte inválida",
            "url": "ftp://example.com/arquivo",
            "descricao": "",
        }, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["url"])
        self.assertFalse(ProjectLink.objects.filter(turma=self.turma).exists())

    @patch("plataforma.guardiao_consulta.consultar_ameacas", return_value=["NO_MATCH"])
    def test_alterar_url_reinicia_verificacao_e_recoloca_link_na_fila(self, _consulta):
        referencia = ProjectLink.objects.create(
            project=None,
            turma=self.turma,
            label="Fonte inicial",
            url="https://example.com/antigo",
            ameaca_estado="NO_MATCH",
        )
        GuardiaoLinkPendente.objects.filter(pk=referencia.pk).delete()
        edit_url = reverse("plataforma:institutional_class_reference_edit", args=[self.turma.pk, referencia.pk])
        response = self.client.post(edit_url, {
            "label": "Fonte atualizada",
            "url": "https://example.com/novo",
            "descricao": "",
        }, HTTP_HOST="camppg.palaciomental.com.br")
        self.assertEqual(response.status_code, 302)
        referencia.refresh_from_db()
        self.assertEqual(referencia.ameaca_estado, "UNVERIFIED")
        self.assertTrue(GuardiaoLinkPendente.objects.filter(pk=referencia.pk).exists())

    @patch("plataforma.guardiao_ameacas.consultar_ameacas_detalhes")
    def test_ameaca_em_referencia_salva_avisa_professor_responsavel(self, consulta):
        from plataforma.guardiao_ameacas import verificar_links_salvos

        referencia = ProjectLink.objects.create(
            project=None, turma=self.turma, label="Fonte da turma", url="https://example.com/consulta",
        )
        agora = timezone.now()
        consulta.return_value = [{
            "state": "THREAT", "checked_at": agora, "expires_at": agora + timedelta(minutes=10),
        }]
        verificar_links_salvos()
        referencia.refresh_from_db()
        self.assertEqual(referencia.ameaca_estado, "THREAT")
        aviso = Notification.objects.get(recipient=self.professor, kind="guardiao_ameaca")
        self.assertIn(self.turma.nome, aviso.message)
