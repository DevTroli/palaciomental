from datetime import timedelta

from django.utils import timezone

from plataforma.models import (
    EventoCalendario, MembroOrganizacao, Organizacao,
    ProgramaInstitucional, Project, Turma, VinculoProjetoInstitucional,
)
from .base import PortalInstitucionalBase

HOST = "camppg.palaciomental.com.br"


class HomeDiscoveryTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user)
        self.client.force_login(self.user)
        self.autonomous = Project.objects.create(owner=self.user, organizacao=self.organization,
            title="Ideia livre", visibility=Project.VISIBILITY_PUBLIC)
        self.program = ProgramaInstitucional.objects.create(organizacao=self.organization,
            nome="Programa em atividade", slug="ativo", criado_por=self.user, status="publicado")
        classroom = Turma.objects.create(programa=self.program, nome="Turma", criado_por=self.user)
        self.linked = Project.objects.create(owner=self.user, organizacao=self.organization,
            title="Projeto vinculado", visibility=Project.VISIBILITY_PUBLIC)
        VinculoProjetoInstitucional.objects.create(projeto=self.linked, turma=classroom, vinculado_por=self.user)

    def test_columns_and_see_more_keep_the_same_project_scope(self):
        response = self.client.get("/", HTTP_HOST=HOST)
        self.assertEqual([p.pk for p in response.context["projetos_autonomos"]], [self.autonomous.pk])
        self.assertEqual([p.pk for p in response.context["projetos_vinculados"]], [self.linked.pk])
        for kind, present, absent in (("autonomo", self.autonomous, self.linked), ("vinculado", self.linked, self.autonomous)):
            response = self.client.get("/projetos/", {"tipo": kind}, HTTP_HOST=HOST)
            self.assertContains(response, present.title)
            self.assertNotContains(response, absent.title)
            self.assertContains(response, f'name="tipo" value="{kind}"')

    def test_draft_program_and_private_projects_do_not_enter_discovery_columns(self):
        self.program.status = "rascunho"
        self.program.save()
        Project.objects.create(owner=self.user, organizacao=self.organization,
            title="Meu projeto privado", visibility=Project.VISIBILITY_PRIVATE)
        response = self.client.get("/", HTTP_HOST=HOST)
        self.assertEqual(response.context["total_vinculados"], 0)
        self.assertNotContains(response, "Meu projeto privado")
        self.assertEqual(list(response.context["projetos_vinculados"]), [])
        response = self.client.get("/projetos/", {"tipo": "vinculado"}, HTTP_HOST=HOST)
        self.assertNotContains(response, self.linked.title)

    def test_four_card_preview_keeps_full_count_and_no_program_or_class_blocks(self):
        for number in range(5):
            Project.objects.create(owner=self.user, organizacao=self.organization,
                title=f"Ideia {number}", visibility=Project.VISIBILITY_PUBLIC)
        response = self.client.get("/", HTTP_HOST=HOST)
        self.assertEqual(len(response.context["projetos_autonomos"]), 4)
        self.assertEqual(response.context["total_autonomos"], 6)
        self.assertNotContains(response, "Turmas elegíveis")
        self.assertNotContains(response, "Programas ativos")
        self.assertContains(response, '?tipo=autonomo')
        self.assertContains(response, '?tipo=vinculado')

    def test_agenda_preview_only_shows_upcoming_events_of_the_current_user_and_tenant(self):
        today = timezone.localdate()
        visible = []
        for day in range(3):
            visible.append(EventoCalendario.objects.create(organizacao=self.organization,
                aluno=self.user, titulo=f"Meu compromisso {day}", data=today + timedelta(days=day)))
        other = Organizacao.objects.create(nome="Outro ambiente", slug="outro", status="ativa")
        hidden = [
            EventoCalendario.objects.create(organizacao=other, aluno=self.user, titulo="Evento de outro tenant", data=today),
            EventoCalendario.objects.create(organizacao=self.organization, aluno=self.pm_staff, titulo="Evento de outra pessoa", data=today),
            EventoCalendario.objects.create(organizacao=self.organization, aluno=self.user, titulo="Compromisso passado", data=today-timedelta(days=1)),
            EventoCalendario.objects.create(organizacao=self.organization, aluno=self.user, titulo="Entrega concluída", data=today, tipo="trabalho", status="entregue"),
        ]
        response = self.client.get("/", HTTP_HOST=HOST)
        self.assertEqual([event.pk for event in response.context["agenda_proximos"]], [event.pk for event in visible[:2]])
        for event in hidden + visible[2:]:
            self.assertNotContains(response, event.titulo)
        self.assertContains(response, f"?ano={today.year}&amp;mes={today.month}")

    def test_empty_agenda_has_a_real_create_event_destination(self):
        response = self.client.get("/", HTTP_HOST=HOST)
        self.assertContains(response, "Nenhum compromisso próximo.")
        self.assertContains(response, 'href="/calendario/novo/"')
        self.assertNotContains(response, "Conhecimento que transforma")
        self.assertNotContains(response, 'class="camp-sidebar-foot"')
