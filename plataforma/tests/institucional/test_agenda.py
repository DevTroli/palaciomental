from datetime import date, time, timedelta
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from plataforma.models import (
    CollaborationRequest,
    DominioOrganizacao,
    MemberProfile,
    MembroOrganizacao,
    Organizacao,
    Project,
    ProjectMember,
)

from plataforma.models import EventoCalendario

HOST = "camp.localhost"


@override_settings(ALLOWED_HOSTS=["*"], DEBUG=True)
class AgendaTestCase(TestCase):
    """Base com organização, domínio e dois alunos afiliados."""

    @classmethod
    def setUpTestData(cls):
        cls.organizacao = Organizacao.objects.create(slug="camp", nome="CAMP", status=Organizacao.STATUS_ATIVA)
        DominioOrganizacao.objects.create(
            organizacao=cls.organizacao,
            hostname=HOST,
            principal=True,
        )
        User = get_user_model()
        cls.aluno = User.objects.create_user(
            "aluno", password="senha-forte", first_name="Iago"
        )
        cls.outro = User.objects.create_user(
            "outro", password="senha-forte", first_name="Mariana"
        )
        for usuario in (cls.aluno, cls.outro):
            MembroOrganizacao.objects.create(
                organizacao=cls.organizacao,
                usuario=usuario,
                papel=MembroOrganizacao.PAPEL_MEMBRO,
                status=MembroOrganizacao.STATUS_ATIVA,
            )
        cls.projeto = Project.objects.create(
            owner=cls.aluno,
            organizacao=cls.organizacao,
            title="Projeto do aluno",
            direction="Direção do projeto.",
            category="Educação",
            status=Project.STATUS_ACTIVE,
        )
        cls.projeto_aberto = Project.objects.create(
            owner=cls.outro,
            organizacao=cls.organizacao,
            title="Projeto aberto",
            direction="Um projeto que busca gente para construir junto.",
            category="Pesquisa",
            status=Project.STATUS_ACTIVE,
            visibility=Project.VISIBILITY_PUBLIC,
            seeking_collaborators=True,
            collaboration_description="Pessoa para pesquisa e prototipação.",
        )
        cls.projeto_privado = Project.objects.create(
            owner=cls.outro,
            organizacao=cls.organizacao,
            title="Projeto privado",
            direction="Projeto que não deve aparecer na exploração.",
            category="Pesquisa",
            status=Project.STATUS_ACTIVE,
            visibility=Project.VISIBILITY_PRIVATE,
            seeking_collaborators=True,
        )

    def setUp(self):
        self.client.force_login(self.aluno)

    def get(self, url, data=None, **extra):
        return self.client.get(url, data or {}, HTTP_HOST=HOST, **extra)

    def post(self, url, data=None, **extra):
        return self.client.post(url, data or {}, HTTP_HOST=HOST, **extra)

    def evento(self, **kwargs):
        dados = {
            "organizacao": self.organizacao,
            "aluno": self.aluno,
            "titulo": "Entrega de teste",
            "tipo": EventoCalendario.TIPO_TRABALHO,
            "data": date.today(),
            "horario": time(23, 59),
            "status": EventoCalendario.STATUS_PENDENTE,
        }
        dados.update(kwargs)
        return EventoCalendario.objects.create(**dados)


class CalendarTests(AgendaTestCase):
    def test_calendario_exige_autenticacao(self):
        self.client.logout()
        response = self.get(reverse("plataforma:calendar"))
        self.assertRedirects(
            response,
            "/entrar/?next=/calendario/",
            fetch_redirect_response=False,
        )

    def test_calendario_mostra_apenas_eventos_do_aluno(self):
        self.evento(titulo="Entrega própria")
        self.evento(aluno=self.outro, titulo="Entrega alheia")

        response = self.get(reverse("plataforma:calendar"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrega própria")
        self.assertNotContains(response, "Entrega alheia")
        self.assertContains(response, "Trabalhos para entregar")
        self.assertContains(response, "Atividades do aluno")
        self.assertNotContains(response, "Membro")

    def test_calendario_ignora_parametros_invalidos(self):
        response = self.get(reverse("plataforma:calendar"), {"ano": "abc", "mes": "99"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ano"], date.today().year)
        self.assertEqual(response.context["mes"], date.today().month)

    def test_trabalhos_atrasados_continuam_pendentes(self):
        atrasado = self.evento(
            titulo="Entrega atrasada",
            data=date.today() - timedelta(days=10),
        )

        response = self.get(reverse("plataforma:calendar"))

        self.assertIn(atrasado, response.context["trabalhos_pendentes"])
        self.assertContains(response, "Entrega atrasada")

    def test_calendario_exibe_descricao_do_trabalho_publicado(self):
        self.evento(
            titulo="Entrega com instruções",
            descricao="Anexe o relatório final no projeto.",
            origem=EventoCalendario.ORIGEM_ORGANIZACAO,
            data=date.today(),
        )
        response = self.get(reverse("plataforma:calendar"))
        self.assertContains(response, "Anexe o relatório final no projeto.")

    def test_marcar_entrega_altera_status(self):
        trabalho = self.evento()

        response = self.post(reverse("plataforma:calendar_toggle", args=[trabalho.pk]))

        self.assertRedirects(
            response,
            f"/calendario/?ano={trabalho.data.year}&mes={trabalho.data.month}",
            fetch_redirect_response=False,
        )
        trabalho.refresh_from_db()
        self.assertEqual(trabalho.status, EventoCalendario.STATUS_ENTREGUE)

    def test_nao_permite_entregar_evento_de_outro_aluno(self):
        alheio = self.evento(aluno=self.outro)

        response = self.post(reverse("plataforma:calendar_toggle", args=[alheio.pk]))

        self.assertEqual(response.status_code, 404)
        alheio.refresh_from_db()
        self.assertEqual(alheio.status, EventoCalendario.STATUS_PENDENTE)


class CalendarEventCrudTests(AgendaTestCase):
    def test_aluno_cria_evento_pessoal(self):
        response = self.post(
            reverse("plataforma:event_create"),
            {
                "titulo": "Revisão com o grupo",
                "descricao": "Levar anotações.",
                "tipo": EventoCalendario.TIPO_TRABALHO,
                "data": date.today().isoformat(),
                "horario": "19:30",
                "projeto": self.projeto.pk,
            },
        )

        evento = EventoCalendario.objects.get(titulo="Revisão com o grupo")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(evento.aluno, self.aluno)
        self.assertEqual(evento.organizacao, self.organizacao)
        self.assertEqual(evento.origem, EventoCalendario.ORIGEM_ALUNO)
        self.assertEqual(evento.status, EventoCalendario.STATUS_PENDENTE)
        self.assertEqual(evento.projeto, self.projeto)

    def test_atividade_criada_fica_confirmada(self):
        self.post(
            reverse("plataforma:event_create"),
            {
                "titulo": "Estudo individual",
                "tipo": EventoCalendario.TIPO_ATIVIDADE,
                "data": date.today().isoformat(),
            },
        )

        evento = EventoCalendario.objects.get(titulo="Estudo individual")
        self.assertEqual(evento.status, EventoCalendario.STATUS_CONFIRMADO)

    def test_aluno_edita_evento_proprio(self):
        evento = self.evento(
            titulo="Evento original",
            origem=EventoCalendario.ORIGEM_ALUNO,
            tipo=EventoCalendario.TIPO_ATIVIDADE,
        )

        response = self.post(
            reverse("plataforma:event_edit", args=[evento.pk]),
            {
                "titulo": "Evento atualizado",
                "tipo": EventoCalendario.TIPO_ATIVIDADE,
                "data": evento.data.isoformat(),
                "horario": "20:00",
            },
        )

        evento.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(evento.titulo, "Evento atualizado")
        self.assertEqual(evento.horario, time(20, 0))

    def test_aluno_exclui_evento_proprio(self):
        evento = self.evento(
            titulo="Evento para excluir",
            origem=EventoCalendario.ORIGEM_ALUNO,
        )

        response = self.post(reverse("plataforma:event_delete", args=[evento.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(EventoCalendario.objects.filter(pk=evento.pk).exists())

    def test_nao_edita_evento_da_organizacao(self):
        evento = self.evento(titulo="Evento da organização")

        response = self.get(reverse("plataforma:event_edit", args=[evento.pk]))

        self.assertEqual(response.status_code, 404)

    def test_nao_exclui_evento_de_outro_aluno(self):
        evento = self.evento(
            aluno=self.outro,
            titulo="Evento alheio",
            origem=EventoCalendario.ORIGEM_ALUNO,
        )

        response = self.post(reverse("plataforma:event_delete", args=[evento.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(EventoCalendario.objects.filter(pk=evento.pk).exists())

    def test_nao_permite_titulo_duplicado_na_mesma_data(self):
        self.evento(
            titulo="Entrega repetida",
            origem=EventoCalendario.ORIGEM_ALUNO,
        )

        response = self.post(
            reverse("plataforma:event_create"),
            {
                "titulo": "entrega repetida",
                "tipo": EventoCalendario.TIPO_TRABALHO,
                "data": date.today().isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "já tem um evento com este título")
        self.assertEqual(
            EventoCalendario.objects.filter(titulo__iexact="Entrega repetida").count(),
            1,
        )
