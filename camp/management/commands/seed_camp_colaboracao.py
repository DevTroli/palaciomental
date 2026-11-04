from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from listaEspera.models import MembroOrganizacao, Organizacao, Project, ProjectMember

User = get_user_model()

PROJETOS = (
    {
        "titulo": "Rede de Mentoria CAMP",
        "dono": "mariana",
        "categoria": "Educação",
        "direcao": "Conectar alunos experientes a quem está começando uma nova trilha no CAMP.",
        "projeto": "Alunos para mentorar e facilitar encontros em grupo.",
        "tags": "mentoria, comunidade, educação",
        "colegas": ("lucas", "ana"),
    },
    {
        "titulo": "Laboratório de Protótipos",
        "dono": "rafael",
        "categoria": "Tecnologia",
        "direcao": "Transformar ideias do CAMP em protótipos testáveis em poucas semanas.",
        "projeto": "Pessoas para prototipagem, testes e documentação.",
        "tags": "tecnologia, protótipo, produto",
        "colegas": ("bruno", "felipe"),
    },
    {
        "titulo": "Clube de Leitura e Pesquisa",
        "dono": "juliana",
        "categoria": "Pesquisa",
        "direcao": "Criar um espaço de curadoria, leitura e pesquisa aberta para o CAMP.",
        "projeto": "Alunos para curadoria de leituras e encontros mensais.",
        "tags": "pesquisa, leitura, curadoria",
        "colegas": ("ana",),
    },
)


class Command(BaseCommand):
    help = "Cria projetos de demonstração abertos a colaboração no CAMP."

    def add_arguments(self, parser):
        parser.add_argument("--organizacao", help="Nome da organização (padrão: primeira ativa).")

    def handle(self, *args, **options):
        organizacao = self._organizacao(options["organizacao"])
        criados = 0
        atualizados = 0

        for dados in PROJETOS:
            dono = self._aluno(dados["dono"], organizacao)
            projeto, criado = Project.objects.get_or_create(
                owner=dono,
                title=dados["titulo"],
                defaults={
                    "organizacao": organizacao,
                    "direction": dados["direcao"],
                    "category": dados["categoria"],
                    "status": Project.STATUS_ACTIVE,
                    "visibility": Project.VISIBILITY_PUBLIC,
                    "seeking_collaborators": True,
                    "collaboration_description": dados["projeto"],
                    "tags": dados["tags"],
                },
            )
            if criado:
                criados += 1
            else:
                projeto.organizacao = organizacao
                projeto.direction = dados["direcao"]
                projeto.category = dados["categoria"]
                projeto.status = Project.STATUS_ACTIVE
                projeto.visibility = Project.VISIBILITY_PUBLIC
                projeto.seeking_collaborators = True
                projeto.collaboration_description = dados["projeto"]
                projeto.tags = dados["tags"]
                projeto.save(
                    update_fields=[
                        "organizacao",
                        "direction",
                        "category",
                        "status",
                        "visibility",
                        "seeking_collaborators",
                        "collaboration_description",
                        "tags",
                        "updated_at",
                    ]
                )
                atualizados += 1

            for username in dados["colegas"]:
                colega = self._aluno(username, organizacao)
                if colega.pk == dono.pk:
                    continue
                ProjectMember.objects.get_or_create(
                    project=projeto,
                    user=colega,
                    defaults={"role": "Colaborador"},
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"{criados} projeto(s) criado(s) e {atualizados} atualizado(s) "
                f"para colaboração em {organizacao.nome}."
            )
        )

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
        try:
            usuario = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"Usuário “{username}” não encontrado.") from exc
        if not MembroOrganizacao.objects.filter(
            organizacao=organizacao,
            usuario=usuario,
            status=MembroOrganizacao.STATUS_ATIVA,
        ).exists():
            raise CommandError(f"O usuário “{username}” não é aluno ativo de {organizacao.nome}.")
        return usuario
