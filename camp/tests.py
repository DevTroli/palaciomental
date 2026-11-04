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

from .models import EventoCalendario

HOST = "camp.localhost"


@override_settings(ALLOWED_HOSTS=["*"], DEBUG=True)
class CampTestCase(TestCase):
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


class CampAcessoTests(CampTestCase):
    def test_acesso_camp_sem_login_redireciona_para_cadastro(self):
        self.client.logout()

        response = self.get(reverse("camp:dashboard"))

        self.assertRedirects(
            response,
            "/camp/cadastro/?next=/camp/",
            fetch_redirect_response=False,
        )

    def test_pagina_cadastro_do_camp_e_publica(self):
        self.client.logout()

        response = self.get(reverse("camp:register"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Criar sua conta no CAMP")
        self.assertContains(response, "Entrar como teste")
        self.assertContains(response, "CAMP-PG")

    def test_pagina_cadastro_redireciona_usuario_logado(self):
        self.client.force_login(self.aluno)

        response = self.get(reverse("camp:register"))

        self.assertRedirects(response, reverse("camp:dashboard"), fetch_redirect_response=False)


class CalendarTests(CampTestCase):
    def test_calendario_exige_autenticacao(self):
        self.client.logout()
        response = self.get(reverse("camp:calendar"))
        self.assertRedirects(
            response,
            "/entrar/camp/?next=/camp/calendario/",
            fetch_redirect_response=False,
        )

    def test_calendario_mostra_apenas_eventos_do_aluno(self):
        self.evento(titulo="Entrega própria")
        self.evento(aluno=self.outro, titulo="Entrega alheia")

        response = self.get(reverse("camp:calendar"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrega própria")
        self.assertNotContains(response, "Entrega alheia")
        self.assertContains(response, "Trabalhos para entregar")
        self.assertContains(response, "Atividades do aluno")
        self.assertNotContains(response, "Membro")

    def test_calendario_ignora_parametros_invalidos(self):
        response = self.get(reverse("camp:calendar"), {"ano": "abc", "mes": "99"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ano"], date.today().year)
        self.assertEqual(response.context["mes"], date.today().month)

    def test_trabalhos_atrasados_continuam_pendentes(self):
        atrasado = self.evento(
            titulo="Entrega atrasada",
            data=date.today() - timedelta(days=10),
        )

        response = self.get(reverse("camp:calendar"))

        self.assertIn(atrasado, response.context["trabalhos_pendentes"])
        self.assertContains(response, "Entrega atrasada")

    def test_marcar_entrega_altera_status(self):
        trabalho = self.evento()

        response = self.post(reverse("camp:calendar_toggle", args=[trabalho.pk]))

        self.assertRedirects(
            response,
            f"/camp/calendario/?ano={trabalho.data.year}&mes={trabalho.data.month}",
            fetch_redirect_response=False,
        )
        trabalho.refresh_from_db()
        self.assertEqual(trabalho.status, EventoCalendario.STATUS_ENTREGUE)

    def test_nao_permite_entregar_evento_de_outro_aluno(self):
        alheio = self.evento(aluno=self.outro)

        response = self.post(reverse("camp:calendar_toggle", args=[alheio.pk]))

        self.assertEqual(response.status_code, 404)
        alheio.refresh_from_db()
        self.assertEqual(alheio.status, EventoCalendario.STATUS_PENDENTE)


class ProfileTests(CampTestCase):
    def test_perfil_mostra_projetos_e_participacoes_do_aluno(self):
        participacao = Project.objects.create(
            owner=self.outro,
            organizacao=self.organizacao,
            title="Projeto em que participo",
            direction="Direção.",
            category="Pesquisa",
        )
        ProjectMember.objects.create(project=participacao, user=self.aluno)

        response = self.get(reverse("camp:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.projeto.title)
        self.assertContains(response, participacao.title)
        self.assertContains(response, "Aluno")

    def test_aluno_cria_projeto_proprio(self):
        response = self.post(
            reverse("camp:project_create"),
            {
                "title": "Novo projeto do aluno",
                "direction": "Uma direção clara.",
                "category": "Tecnologia",
                "status": Project.STATUS_ACTIVE,
                "visibility": Project.VISIBILITY_PRIVATE,
                "tags": "código, pesquisa",
            },
        )

        self.assertRedirects(response, reverse("camp:profile"), fetch_redirect_response=False)
        projeto = Project.objects.get(title="Novo projeto do aluno")
        self.assertEqual(projeto.owner, self.aluno)
        self.assertEqual(projeto.organizacao, self.organizacao)

    def test_aluno_nao_edita_projeto_de_outro(self):
        alheio = Project.objects.create(
            owner=self.outro,
            organizacao=self.organizacao,
            title="Projeto alheio",
            direction="Direção.",
            category="Pesquisa",
        )

        response = self.get(reverse("camp:project_edit", args=[alheio.pk]))

        self.assertEqual(response.status_code, 404)

    def test_perfil_mostra_abas_calendario_e_proximas_atividades(self):
        evento = self.evento(
            titulo="Encontro de sábado",
            data=date.today() + timedelta(days=2),
        )

        response = self.get(reverse("camp:profile"))
        html = response.content.decode()

        self.assertContains(response, "Meus Projetos")
        self.assertContains(response, "Colaborações")
        self.assertContains(response, "Configurações")
        self.assertContains(response, "Meu calendário")
        self.assertContains(response, "Próximas atividades")
        self.assertContains(response, "CAMP - ALUNO")
        self.assertContains(response, evento.titulo)
        self.assertIn('data-profile-tab="projetos"', html)
        self.assertIn('data-profile-panel="colaboracoes"', html)

    def test_perfil_permite_minimizar_calendario(self):
        response = self.get(reverse("camp:profile"))

        self.assertContains(response, "data-calendar-toggle")
        self.assertContains(response, 'aria-controls="perfil-calendario-corpo"')
        self.assertContains(response, "data-calendar-body")
        self.assertContains(response, "Minimizar calendário")

    def test_perfil_mostra_projetos_institucionais(self):
        Project.objects.create(
            owner=self.outro,
            organizacao=self.organizacao,
            title="Projeto institucional aberto",
            direction="Direção.",
            category="Pesquisa",
            visibility=Project.VISIBILITY_PUBLIC,
        )

        response = self.get(reverse("camp:profile"))

        self.assertContains(response, "Projetos Institucionais")
        self.assertContains(response, "Projeto institucional aberto")

    def test_aluno_atualiza_nome_e_email(self):
        response = self.post(
            reverse("camp:profile"),
            {
                "form": "perfil",
                "first_name": "Iago",
                "last_name": "Silva",
                "email": "iago@example.com",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('camp:profile')}?aba=configuracoes",
            fetch_redirect_response=False,
        )
        self.aluno.refresh_from_db()
        self.assertEqual(self.aluno.get_full_name(), "Iago Silva")
        self.assertEqual(self.aluno.email, "iago@example.com")

    def test_aluno_envia_foto_de_perfil(self):
        imagem = SimpleUploadedFile(
            "avatar.png",
            b"\x89PNG\r\n\x1a\nfoto-de-teste",
            content_type="image/png",
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.post(
                    reverse("camp:profile"),
                    {
                        "form": "perfil",
                        "first_name": "Iago",
                        "last_name": "Mendes",
                        "email": "iago@example.com",
                        "avatar": imagem,
                    },
                )

                self.assertRedirects(
                    response,
                    f"{reverse('camp:profile')}?aba=configuracoes",
                    fetch_redirect_response=False,
                )
                perfil = MemberProfile.objects.get(user=self.aluno)
                self.assertTrue(perfil.avatar.name.startswith("avatars/"))
                self.assertTrue((Path(media_root) / perfil.avatar.name).exists())

                pagina = self.get(reverse("camp:profile"), {"aba": "configuracoes"})
                self.assertContains(pagina, perfil.avatar.url)
                self.assertContains(pagina, "camp-profile-avatar-xl")

    def test_aluno_remove_foto_de_perfil(self):
        MemberProfile.objects.create(
            user=self.aluno,
            avatar=SimpleUploadedFile("antiga.png", b"conteudo", content_type="image/png"),
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.post(
                    reverse("camp:profile"),
                    {
                        "form": "perfil",
                        "first_name": "Iago",
                        "last_name": "Mendes",
                        "email": "iago@example.com",
                        "remover_avatar": "on",
                    },
                )

        self.assertRedirects(
            response,
            f"{reverse('camp:profile')}?aba=configuracoes",
            fetch_redirect_response=False,
        )
        perfil = MemberProfile.objects.get(user=self.aluno)
        self.assertFalse(perfil.avatar)

    def test_aluno_troca_a_senha(self):
        response = self.post(
            reverse("camp:profile"),
            {
                "form": "senha",
                "old_password": "senha-forte",
                "new_password1": "NovaSenha!2026",
                "new_password2": "NovaSenha!2026",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('camp:profile')}?aba=configuracoes",
            fetch_redirect_response=False,
        )
        self.aluno.refresh_from_db()
        self.assertTrue(self.aluno.check_password("NovaSenha!2026"))


class CalendarEventCrudTests(CampTestCase):
    def test_aluno_cria_evento_pessoal(self):
        response = self.post(
            reverse("camp:event_create"),
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
            reverse("camp:event_create"),
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
            reverse("camp:event_edit", args=[evento.pk]),
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

        response = self.post(reverse("camp:event_delete", args=[evento.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(EventoCalendario.objects.filter(pk=evento.pk).exists())

    def test_nao_edita_evento_da_organizacao(self):
        evento = self.evento(titulo="Evento da organização")

        response = self.get(reverse("camp:event_edit", args=[evento.pk]))

        self.assertEqual(response.status_code, 404)

    def test_nao_exclui_evento_de_outro_aluno(self):
        evento = self.evento(
            aluno=self.outro,
            titulo="Evento alheio",
            origem=EventoCalendario.ORIGEM_ALUNO,
        )

        response = self.post(reverse("camp:event_delete", args=[evento.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(EventoCalendario.objects.filter(pk=evento.pk).exists())

    def test_nao_permite_titulo_duplicado_na_mesma_data(self):
        self.evento(
            titulo="Entrega repetida",
            origem=EventoCalendario.ORIGEM_ALUNO,
        )

        response = self.post(
            reverse("camp:event_create"),
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


class ExploreTests(CampTestCase):
    def test_explorar_mostra_projetos_abertos(self):
        response = self.get(reverse("camp:explore"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Projeto aberto")
        self.assertContains(response, "Participar da colaboração")
        self.assertNotContains(response, "Projeto privado")
        self.assertNotContains(response, "Projeto do aluno")
        self.assertEqual(response.context["nav_ativo"], "explorar")

    def test_busca_filtra_projetos(self):
        response = self.get(reverse("camp:explore"), {"q": "prototipação"})

        self.assertContains(response, "Projeto aberto")

        response = self.get(reverse("camp:explore"), {"q": "assunto inexistente"})

        self.assertNotContains(response, "camp-open-title")
        self.assertContains(response, "Nenhum projeto aberto encontrado")

    def test_vista_de_alunos_mostra_colegas(self):
        response = self.get(reverse("camp:explore"), {"vista": "alunos"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mariana")
        self.assertContains(response, "@outro")
        self.assertNotContains(response, "@aluno")
        self.assertEqual(response.context["nav_ativo"], "alunos")

    def test_filtro_por_aluno_mostra_seus_projetos(self):
        response = self.get(
            reverse("camp:explore"),
            {"aluno": self.outro.username},
        )

        self.assertContains(response, "Projeto aberto")
        self.assertContains(response, "Mostrando projetos de")
        self.assertContains(response, "Mariana")

    def test_aluno_participa_de_projeto_aberto(self):
        response = self.post(
            reverse("camp:join_project", args=[self.projeto_aberto.pk]),
            {"next": "/camp/explorar/?vista=projetos"},
        )

        self.assertRedirects(
            response,
            "/camp/explorar/?vista=projetos",
            fetch_redirect_response=False,
        )
        self.assertTrue(
            ProjectMember.objects.filter(
                project=self.projeto_aberto,
                user=self.aluno,
            ).exists()
        )

    def test_participar_duas_vezes_nao_duplica(self):
        self.post(reverse("camp:join_project", args=[self.projeto_aberto.pk]))
        self.post(reverse("camp:join_project", args=[self.projeto_aberto.pk]))

        self.assertEqual(
            ProjectMember.objects.filter(
                project=self.projeto_aberto,
                user=self.aluno,
            ).count(),
            1,
        )

    def test_nao_participa_de_projeto_privado(self):
        response = self.post(reverse("camp:join_project", args=[self.projeto_privado.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            ProjectMember.objects.filter(
                project=self.projeto_privado,
                user=self.aluno,
            ).exists()
        )

    def test_aluno_sai_da_colaboracao(self):
        ProjectMember.objects.create(project=self.projeto_aberto, user=self.aluno)

        response = self.post(
            reverse("camp:leave_project", args=[self.projeto_aberto.pk])
        )

        self.assertRedirects(response, reverse("camp:profile"), fetch_redirect_response=False)
        self.assertFalse(
            ProjectMember.objects.filter(
                project=self.projeto_aberto,
                user=self.aluno,
            ).exists()
        )

    def test_perfil_mostra_acao_de_sair_da_colaboracao(self):
        ProjectMember.objects.create(project=self.projeto_aberto, user=self.aluno)

        response = self.get(reverse("camp:profile"))

        self.assertContains(response, "Sair da colaboração")


class TopbarAndInboxTests(CampTestCase):
    def test_topbar_mostra_novo_logo_nome_e_atalhos(self):
        response = self.get(reverse("camp:dashboard"))

        self.assertContains(response, "logo_camp2.png")
        self.assertContains(response, "CAMP-PG")
        self.assertContains(response, 'class="camp-brand" href="/camp/"')
        self.assertContains(response, "palacio_camp_logo.png")
        self.assertContains(response, "Caixa de entrada")
        self.assertContains(response, "MEU ESPAÇO")
        self.assertContains(response, "Logout")
        self.assertContains(response, "Buscar projetos e alunos")

    def test_footer_credita_palacio_mental(self):
        response = self.get(reverse("camp:dashboard"))

        self.assertContains(response, "criado por Palácio Mental")

    def test_aluno_nao_ve_opcao_de_gestao(self):
        response = self.get(reverse("camp:dashboard"))

        self.assertNotContains(response, "Painel do gestor")

    def test_gestor_ve_opcao_de_gestao(self):
        MembroOrganizacao.objects.filter(usuario=self.aluno).update(
            papel=MembroOrganizacao.PAPEL_GESTOR
        )

        response = self.get(reverse("camp:dashboard"))

        self.assertContains(response, "Painel do gestor")
        self.assertContains(response, "Gestão")

    def test_inbox_lista_atividade_futura_da_organizacao(self):
        self.evento(
            titulo="Oficina de protótipos",
            tipo=EventoCalendario.TIPO_ATIVIDADE,
            origem=EventoCalendario.ORIGEM_ORGANIZACAO,
            data=date.today() + timedelta(days=2),
        )

        response = self.get(reverse("camp:inbox"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Oficina de protótipos")
        self.assertContains(response, "Novas atividades")
        self.assertNotContains(response, "Membro")

    def test_inbox_nao_lista_atividade_de_outro_aluno(self):
        self.evento(
            aluno=self.outro,
            titulo="Atividade alheia",
            tipo=EventoCalendario.TIPO_ATIVIDADE,
            origem=EventoCalendario.ORIGEM_ORGANIZACAO,
            data=date.today() + timedelta(days=2),
        )

        response = self.get(reverse("camp:inbox"))

        self.assertNotContains(response, "Atividade alheia")

    def test_inbox_lista_novo_colaborador_do_projeto_do_aluno(self):
        ProjectMember.objects.create(project=self.projeto, user=self.outro)

        response = self.get(reverse("camp:inbox"))

        self.assertContains(response, "Mariana")
        self.assertContains(response, "Projeto do aluno")
        self.assertContains(response, "Novos colaboradores")

    def test_badge_conta_novidades_e_zera_apos_visita(self):
        ProjectMember.objects.create(project=self.projeto, user=self.outro)

        response = self.get(reverse("camp:dashboard"))
        self.assertEqual(response.context["inbox_novas"], 1)

        self.get(reverse("camp:inbox"))
        response = self.get(reverse("camp:dashboard"))

        self.assertEqual(response.context["inbox_novas"], 0)

    def test_aceitar_pedido_cria_participacao(self):
        pedido = CollaborationRequest.objects.create(
            project=self.projeto,
            requester=self.outro,
            message="Quero ajudar no projeto.",
        )

        response = self.post(
            reverse("camp:inbox_decide", args=[pedido.pk]),
            {"decision": CollaborationRequest.ACCEPTED},
        )

        self.assertRedirects(response, reverse("camp:inbox"), fetch_redirect_response=False)
        self.assertTrue(
            ProjectMember.objects.filter(project=self.projeto, user=self.outro).exists()
        )
        self.assertFalse(CollaborationRequest.objects.filter(pk=pedido.pk).exists())

    def test_recusar_pedido_nao_cria_participacao(self):
        pedido = CollaborationRequest.objects.create(
            project=self.projeto,
            requester=self.outro,
            message="Quero ajudar no projeto.",
        )

        response = self.post(
            reverse("camp:inbox_decide", args=[pedido.pk]),
            {"decision": CollaborationRequest.REJECTED},
        )

        self.assertRedirects(response, reverse("camp:inbox"), fetch_redirect_response=False)
        self.assertFalse(
            ProjectMember.objects.filter(project=self.projeto, user=self.outro).exists()
        )
        self.assertFalse(CollaborationRequest.objects.filter(pk=pedido.pk).exists())

    def test_nao_decide_pedido_de_projeto_alheio(self):
        pedido = CollaborationRequest.objects.create(
            project=self.projeto_aberto,
            requester=self.outro,
            message="Quero ajudar no projeto.",
        )

        response = self.post(
            reverse("camp:inbox_decide", args=[pedido.pk]),
            {"decision": CollaborationRequest.ACCEPTED},
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(CollaborationRequest.objects.filter(pk=pedido.pk).exists())


class ManageTests(CampTestCase):
    def test_aluno_nao_acessa_painel_de_gestao(self):
        response = self.get(reverse("camp:manage"))

        self.assertEqual(response.status_code, 404)

    def test_professor_acessa_painel_de_gestao(self):
        MembroOrganizacao.objects.filter(usuario=self.aluno).update(
            papel=MembroOrganizacao.PAPEL_PROFESSOR
        )

        response = self.get(reverse("camp:manage"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Painel do gestor")
        self.assertContains(response, "Projetos da organização")
        self.assertContains(response, "Mariana")
        self.assertContains(response, "Projeto do aluno")

    def test_administrador_acessa_painel_de_gestao(self):
        self.aluno.is_staff = True
        self.aluno.save(update_fields=["is_staff"])

        response = self.get(reverse("camp:manage"))

        self.assertEqual(response.status_code, 200)

    def test_logout_encerra_a_sessao(self):
        response = self.post(reverse("camp:logout"))

        self.assertRedirects(response, "/entrar/", fetch_redirect_response=False)
        response = self.get(reverse("camp:dashboard"))
        self.assertEqual(response.status_code, 302)


class DashboardAboutTests(CampTestCase):
    def test_atalho_mais_fica_entre_inbox_e_busca(self):
        response = self.get(reverse("camp:dashboard"))
        html = response.content.decode()

        inbox = html.index("Caixa de entrada")
        mais = html.index("Criar novo projeto")
        busca = html.index("Buscar no CAMP")

        self.assertLess(inbox, mais)
        self.assertLess(mais, busca)
        self.assertContains(response, reverse("camp:project_create"))

    def test_banner_tem_emblema_sobreposto(self):
        response = self.get(reverse("camp:dashboard"))

        self.assertContains(response, "camp-hero--emblem")
        self.assertContains(response, "camp-hero-emblem")
        self.assertContains(response, "logo_camp2.png")

    def test_historia_e_acesso_rapido_abaixo_do_banner(self):
        response = self.get(reverse("camp:dashboard"))
        html = response.content.decode()

        self.assertContains(response, "Nossa história")
        self.assertContains(
            response,
            "Circulo de Amigos do Menor Patrulheiro de Praia Grande",
        )
        self.assertContains(response, "Teodósio de Augustinis")
        self.assertContains(response, "CCI07062019 0001")
        self.assertContains(response, "Acesso Rápido")
        self.assertIn("camp-about", html)
        self.assertIn("camp-history", html)
        self.assertNotIn("camp-secondary", html)

    def test_historia_tem_link_ver_mais(self):
        response = self.get(reverse("camp:dashboard"))

        self.assertContains(response, "Ver mais")
        self.assertContains(response, reverse("camp:history"))

    def test_pagina_historia_apresenta_informacoes(self):
        response = self.get(reverse("camp:history"))

        self.assertContains(response, "Nossa história")
        self.assertContains(response, "Como tudo começou")
        self.assertContains(response, "Teodósio de Augustinis")
        self.assertContains(response, "CCI07062019 0001")
        self.assertContains(response, "Linha do tempo")
        self.assertContains(response, "Voltar ao início")

    def test_hero_usa_os_textos_do_camp(self):
        response = self.get(reverse("camp:dashboard"))
        html = response.content.decode()

        self.assertContains(response, "Bem-vindo ao seu espaço")
        self.assertContains(response, "Aqui seus projetos institucionais ganham forma")

        start = html.index('class="camp-hero')
        hero = html[start:html.index("</section>", start)]
        self.assertNotIn("Palácio Mental", hero)

    def test_sidebar_tem_menu_recolhivel_e_botao_hamburger(self):
        response = self.get(reverse("camp:dashboard"))

        self.assertContains(response, 'class="camp-sidebar"')
        self.assertContains(response, 'class="camp-menu-toggle"')
        self.assertContains(response, 'aria-controls="camp-sidebar"')


class QuickAccessTests(CampTestCase):
    def test_acesso_rapido_tem_os_novos_atalhos_na_ordem(self):
        response = self.get(reverse("camp:dashboard"))
        html = response.content.decode()

        labels = [
            "Novo Projeto",
            "Explorar",
            "Agenda de atividades",
            "Orientações",
            "Meus grupos",
        ]
        start = html.index('class="camp-quick-grid"')
        grid = html[start:html.index("</section>", start)]
        positions = [grid.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(html.count('class="camp-quick"'), 5)
        self.assertContains(response, reverse("camp:calendar"))
        self.assertContains(response, 'data-em-breve="Meus grupos"')


class HomeProjectsTests(CampTestCase):
    def test_dashboard_mostra_tres_colunas_de_projetos(self):
        response = self.get(reverse("camp:dashboard"))
        html = response.content.decode()

        pessoais = html.index("Projetos Pessoais")
        institucionais = html.index("Projetos Institucionais")
        ranking = html.index("Ranking de Projetos")
        self.assertLess(pessoais, institucionais)
        self.assertLess(institucionais, ranking)

        self.assertContains(response, "Projeto do aluno")
        self.assertContains(response, "Projeto aberto")
        self.assertNotContains(response, "Projeto privado")
        self.assertContains(response, "camp-home-columns")
        self.assertContains(response, "camp-project-card")
        self.assertContains(response, "camp-project-tag")
        self.assertContains(response, "camp-project-meta")

    def test_dashboard_limita_um_projeto_por_coluna(self):
        Project.objects.create(
            owner=self.aluno,
            organizacao=self.organizacao,
            title="Segundo projeto pessoal",
            status=Project.STATUS_ACTIVE,
        )
        Project.objects.create(
            owner=self.outro,
            organizacao=self.organizacao,
            title="Segundo projeto institucional",
            status=Project.STATUS_ACTIVE,
            visibility=Project.VISIBILITY_PUBLIC,
        )

        response = self.get(reverse("camp:dashboard"))
        html = response.content.decode()

        start = html.index('id="pessoais-titulo"')
        pessoais = html[start : html.index('id="institucionais-titulo"', start)]
        self.assertEqual(pessoais.count('<article class="camp-project-card">'), 1)

        start = html.index('id="institucionais-titulo"')
        institucionais = html[start : html.index('id="ranking-titulo"', start)]
        self.assertEqual(
            institucionais.count('<article class="camp-project-card">'), 1
        )
