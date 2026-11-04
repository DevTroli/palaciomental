from datetime import date, time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q

from camp.models import EventoCalendario
from listaEspera.models import MembroOrganizacao, Organizacao, Project

User = get_user_model()

DIAS_ATIVIDADES = (4, 11, 18, 25)
DIAS_TRABALHOS = (7, 14, 21, 28)
HORARIOS = (time(19, 0), time(19, 30), time(20, 0), time(18, 30))


class Command(BaseCommand):
    help = "Cria eventos de demonstração no calendário do CAMP."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", help="Username do aluno (padrão: aluno de demonstração).")
        parser.add_argument("--organizacao", help="Nome da organização (padrão: primeira ativa).")
        parser.add_argument("--ano", type=int, help="Ano do calendário (padrão: ano atual).")
        parser.add_argument("--mes", type=int, help="Mês do calendário (padrão: mês atual).")
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Remove os eventos do aluno no mês antes de recriar.",
        )

    def handle(self, *args, **options):
        hoje = date.today()
        ano = options["ano"] or hoje.year
        mes = options["mes"] or hoje.month
        if not 1 <= mes <= 12:
            raise CommandError("Informe um mês entre 1 e 12.")

        organizacao = self._organizacao(options["organizacao"])
        aluno = self._aluno(options["usuario"], organizacao)

        if options["limpar"]:
            removidos, _ = EventoCalendario.objects.filter(
                organizacao=organizacao,
                aluno=aluno,
                data__year=ano,
                data__month=mes,
            ).delete()
            self.stdout.write(f"Removidos {removidos} evento(s) de {mes:02d}/{ano}.")

        projetos = list(
            Project.objects.filter(organizacao=organizacao)
            .filter(Q(owner=aluno) | Q(memberships__user=aluno))
            .distinct()
            .order_by("title")[:4]
        )
        if not projetos:
            projetos = [None]

        # O mês atual e o seguinte garantem conteúdo mesmo no fim do mês.
        meses = [(ano, mes), self._mes_seguinte(ano, mes)]
        criados = 0
        for ano_alvo, mes_alvo in meses:
            criados += self._semear_mes(
                organizacao,
                aluno,
                projetos,
                ano_alvo,
                mes_alvo,
                hoje,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{criados} evento(s) criado(s) para {aluno.username} "
                f"em {mes:02d}/{ano} e {meses[1][1]:02d}/{meses[1][0]}."
            )
        )

    def _semear_mes(self, organizacao, aluno, projetos, ano, mes, hoje):
        criados = 0
        for indice, dia in enumerate(DIAS_ATIVIDADES):
            projeto = projetos[indice % len(projetos)]
            titulo = f"Encontro · {projeto.title}" if projeto else "Aula aberta CAMP"
            criados += self._criar(
                organizacao,
                aluno,
                projeto,
                titulo,
                "Encontro da atividade com o grupo.",
                EventoCalendario.TIPO_ATIVIDADE,
                date(ano, mes, dia),
                HORARIOS[indice % len(HORARIOS)],
                EventoCalendario.STATUS_CONFIRMADO,
            )

        for indice, dia in enumerate(DIAS_TRABALHOS):
            projeto = projetos[indice % len(projetos)]
            titulo = f"Entrega · {projeto.title}" if projeto else "Entrega · Atividade CAMP"
            data_entrega = date(ano, mes, dia)
            status = (
                EventoCalendario.STATUS_ENTREGUE
                if data_entrega < hoje
                else EventoCalendario.STATUS_PENDENTE
            )
            criados += self._criar(
                organizacao,
                aluno,
                projeto,
                titulo,
                "Trabalho com prazo de entrega definido pelo CAMP.",
                EventoCalendario.TIPO_TRABALHO,
                data_entrega,
                time(23, 59),
                status,
            )

        # Exemplos de eventos pessoais, que o aluno pode editar e excluir.
        criados += self._criar(
            organizacao,
            aluno,
            None,
            "Estudo individual",
            "Bloco reservado para revisar os conteúdos do mês.",
            EventoCalendario.TIPO_ATIVIDADE,
            date(ano, mes, 2),
            time(18, 0),
            EventoCalendario.STATUS_CONFIRMADO,
            origem=EventoCalendario.ORIGEM_ALUNO,
        )
        data_pessoal = date(ano, mes, 9)
        criados += self._criar(
            organizacao,
            aluno,
            None,
            "Organizar entregas do mês",
            "Revisar prazos e preparar os materiais das próximas entregas.",
            EventoCalendario.TIPO_TRABALHO,
            data_pessoal,
            time(20, 0),
            (
                EventoCalendario.STATUS_ENTREGUE
                if data_pessoal < hoje
                else EventoCalendario.STATUS_PENDENTE
            ),
            origem=EventoCalendario.ORIGEM_ALUNO,
        )
        return criados

    def _criar(
        self,
        organizacao,
        aluno,
        projeto,
        titulo,
        descricao,
        tipo,
        data,
        horario,
        status,
        origem=EventoCalendario.ORIGEM_ORGANIZACAO,
    ):
        _, criado = EventoCalendario.objects.get_or_create(
            organizacao=organizacao,
            aluno=aluno,
            tipo=tipo,
            titulo=titulo,
            data=data,
            defaults={
                "projeto": projeto,
                "descricao": descricao,
                "horario": horario,
                "status": status,
                "origem": origem,
            },
        )
        return 1 if criado else 0

    @staticmethod
    def _mes_seguinte(ano, mes):
        if mes == 12:
            return ano + 1, 1
        return ano, mes + 1

    def _organizacao(self, nome):
        organizacoes = Organizacao.objects.filter(status=Organizacao.STATUS_ATIVA)
        if nome:
            try:
                return organizacoes.get(nome__iexact=nome)
            except Organizacao.DoesNotExist as exc:
                raise CommandError(f"Organização “{nome}” não encontrada.") from exc
        organizacao = organizacoes.order_by("nome").first()
        if organizacao is None:
            raise CommandError("Nenhuma organização ativa encontrada.")
        return organizacao

    def _aluno(self, username, organizacao):
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist as exc:
                raise CommandError(f"Usuário “{username}” não encontrado.") from exc

        membro = (
            MembroOrganizacao.objects.filter(
                organizacao=organizacao,
                status=MembroOrganizacao.STATUS_ATIVA,
            )
            .select_related("usuario")
            .annotate(
                total_projetos=Count("usuario__owned_projects", distinct=True),
                total_participacoes=Count("usuario__project_memberships", distinct=True),
            )
            .order_by("-total_projetos", "-total_participacoes", "usuario__username")
            .first()
        )
        if membro is None:
            raise CommandError("Nenhum aluno ativo encontrado.")
        return membro.usuario
