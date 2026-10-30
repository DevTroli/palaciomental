from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
import uuid

from .validators import CORES_SEMANTICAS, ROTULOS_CORES, caminho_logo, validar_logo


class Organizacao(models.Model):
    """Tenant institucional do Palácio Mental."""

    STATUS_CONFIGURANDO = "configurando"
    STATUS_ATIVA = "ativa"
    STATUS_SUSPENSA = "suspensa"
    STATUS_ARQUIVADA = "arquivada"
    STATUS_CHOICES = (
        (STATUS_CONFIGURANDO, "Em configuração"),
        (STATUS_ATIVA, "Ativa"),
        (STATUS_SUSPENSA, "Suspensa"),
        (STATUS_ARQUIVADA, "Arquivada"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField("Identificador", max_length=80, unique=True)
    nome = models.CharField("Nome", max_length=160)
    nome_legal = models.CharField("Nome legal", max_length=200, blank=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_CONFIGURANDO)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Organização"
        verbose_name_plural = "Organizações"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class IdentidadeOrganizacao(models.Model):
    """Configuração visual controlada pelo tenant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacao = models.OneToOneField(
        Organizacao,
        on_delete=models.CASCADE,
        related_name="identidade",
        verbose_name="Organização",
    )
    nome_exibicao = models.CharField("Nome de exibição", max_length=160, blank=True)
    logo = models.ImageField("Logo", upload_to=caminho_logo, validators=[validar_logo], blank=True)
    cor_primaria = models.CharField("Cor primária", max_length=40, choices=tuple((key, ROTULOS_CORES[key]) for key in CORES_SEMANTICAS), blank=True)
    cor_destaque = models.CharField("Cor de destaque", max_length=40, choices=tuple((key, ROTULOS_CORES[key]) for key in CORES_SEMANTICAS), blank=True)
    cor_fundo = models.CharField("Cor de fundo", max_length=40, choices=tuple((key, ROTULOS_CORES[key]) for key in CORES_SEMANTICAS), blank=True)

    @property
    def completa(self):
        return bool(self.logo and self.cor_primaria and self.cor_destaque and self.cor_fundo)

    class Meta:
        verbose_name = "Identidade visual da organização"
        verbose_name_plural = "Identidades visuais das organizações"

    def __str__(self):
        return self.nome_exibicao or self.organizacao.nome


class DominioOrganizacao(models.Model):
    """Hostname usado para resolver uma organização."""

    TIPO_SUBDOMINIO = "subdominio"
    TIPO_PERSONALIZADO = "personalizado"
    TIPO_CHOICES = (
        (TIPO_SUBDOMINIO, "Subdomínio Palácio Mental"),
        (TIPO_PERSONALIZADO, "Domínio personalizado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacao = models.ForeignKey(
        Organizacao,
        on_delete=models.CASCADE,
        related_name="dominios",
        verbose_name="Organização",
    )
    hostname = models.CharField("Hostname", max_length=255, unique=True)
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, default=TIPO_SUBDOMINIO)
    principal = models.BooleanField("Domínio principal", default=False)
    status_verificacao = models.CharField("Status da verificação", max_length=30, default="ativo")
    verificado_em = models.DateTimeField("Verificado em", null=True, blank=True)

    class Meta:
        verbose_name = "Domínio da organização"
        verbose_name_plural = "Domínios das organizações"
        constraints = [
            models.UniqueConstraint(
                fields=["organizacao", "principal"],
                condition=models.Q(principal=True),
                name="unique_primary_domain_per_organization",
            )
        ]

    def __str__(self):
        return self.hostname


class MembroOrganizacao(models.Model):
    """Afiliação de uma conta a uma organização."""

    PAPEL_PROPRIETARIO = "proprietario"
    PAPEL_GESTOR = "gestor"
    PAPEL_PROFESSOR = "professor"
    PAPEL_MEMBRO = "membro"
    PAPEL_CHOICES = (
        (PAPEL_PROPRIETARIO, "Proprietário"),
        (PAPEL_GESTOR, "Gestor"),
        (PAPEL_PROFESSOR, "Professor"),
        (PAPEL_MEMBRO, "Membro"),
    )
    STATUS_ATIVA = "ativa"
    STATUS_PENDENTE = "pendente"
    STATUS_SUSPENSA = "suspensa"
    STATUS_CHOICES = (
        (STATUS_ATIVA, "Ativa"),
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_SUSPENSA, "Suspensa"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacao = models.ForeignKey(
        Organizacao,
        on_delete=models.CASCADE,
        related_name="afiliacoes",
        verbose_name="Organização",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="afiliacoes_organizacionais",
        verbose_name="Usuário",
    )
    papel = models.CharField("Papel", max_length=20, choices=PAPEL_CHOICES, default=PAPEL_MEMBRO)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVA)
    entrou_em = models.DateTimeField("Entrou em", auto_now_add=True)

    class Meta:
        verbose_name = "Afiliação organizacional"
        verbose_name_plural = "Afiliações organizacionais"
        constraints = [
            models.UniqueConstraint(
                fields=["organizacao", "usuario"],
                name="unique_organization_user_affiliation",
            )
        ]
        indexes = [models.Index(fields=["organizacao", "status"])]

    def __str__(self):
        return f"{self.usuario} — {self.organizacao}"


class ConviteOrganizacao(models.Model):
    """Convite de uso único para entrada controlada no tenant."""

    STATUS_PENDENTE = "pendente"
    STATUS_ACEITO = "aceito"
    STATUS_REVOGADO = "revogado"
    STATUS_CHOICES = (
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_ACEITO, "Aceito"),
        (STATUS_REVOGADO, "Revogado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacao = models.ForeignKey(
        Organizacao,
        on_delete=models.CASCADE,
        related_name="convites",
        verbose_name="Organização",
    )
    convidado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="convites_emitidos",
        verbose_name="Convidado por",
    )
    email = models.EmailField("E-mail convidado")
    papel = models.CharField(
        "Papel inicial",
        max_length=20,
        choices=MembroOrganizacao.PAPEL_CHOICES,
        default=MembroOrganizacao.PAPEL_MEMBRO,
    )
    hash_token = models.CharField("Hash do token", max_length=64, unique=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    expira_em = models.DateTimeField("Expira em")
    aceito_em = models.DateTimeField("Aceito em", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Convite da organização"
        verbose_name_plural = "Convites das organizações"
        indexes = [
            models.Index(fields=["organizacao", "status"]),
            models.Index(fields=["email", "status"]),
        ]

    def __str__(self):
        return f"{self.email} — {self.organizacao}"


class MemberProfile(models.Model):
    """Informações públicas e curtas do portfólio de um membro."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    bio = models.CharField("Biografia", max_length=280, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil de usuário"
        verbose_name_plural = "Perfis de usuários"
        ordering = ["user__username"]

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Project(models.Model):
    STATUS_IDEA = "ideia"
    STATUS_ACTIVE = "ativo"
    STATUS_PAUSED = "pausado"
    STATUS_DONE = "concluido"
    STATUS_CHOICES = (
        (STATUS_IDEA, "Ideia"),
        (STATUS_ACTIVE, "Ativo"),
        (STATUS_PAUSED, "Pausado"),
        (STATUS_DONE, "Concluído"),
    )
    VISIBILITY_PUBLIC = "publico"
    VISIBILITY_PRIVATE = "privado"
    VISIBILITY_RESTRICTED = "restrito"
    VISIBILITY_CHOICES = ((VISIBILITY_PUBLIC, "Público"), (VISIBILITY_RESTRICTED, "Restrito — acesso por link"), (VISIBILITY_PRIVATE, "Privado"))

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_projects")
    organizacao = models.ForeignKey(
        Organizacao,
        on_delete=models.PROTECT,
        related_name="projetos",
        verbose_name="Organização",
        null=True,
        blank=True,
    )
    title = models.CharField("Título", max_length=140)
    direction = models.TextField("Direção", max_length=1000, help_text="Por que este projeto existe?")
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_IDEA)
    visibility = models.CharField("Visibilidade", max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE)
    access_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    category = models.CharField("Categoria", max_length=80)
    tags = models.CharField("Tags", max_length=300, blank=True, help_text="Separe as tags por vírgula")
    seeking_collaborators = models.BooleanField("Buscando colaboradores", default=False)
    collaboration_description = models.CharField("O que procura", max_length=280, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["visibility", "status", "category"])]
        constraints = [models.UniqueConstraint(Lower("title"), "owner", name="unique_owner_project_title_ci")]

    def tag_list(self):
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    def __str__(self):
        return self.title


class ProjectLink(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="links")
    label = models.CharField("Nome do link", max_length=80)
    url = models.URLField("URL", max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Link de projeto"
        verbose_name_plural = "Links de projetos"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.label} — {self.project.title}"


class ProjectMember(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships")
    role = models.CharField("Papel", max_length=80, default="Colaborador")
    can_manage_milestones = models.BooleanField("Pode gerenciar marcos", default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membro de projeto"
        verbose_name_plural = "Membros de projetos"
        constraints = [models.UniqueConstraint(fields=["project", "user"], name="unique_project_member")]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} em {self.project}"


class ProjectComment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_comments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    content = models.TextField("Comentário", max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Comentário de projeto"
        verbose_name_plural = "Comentários de projetos"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comentário de {self.author} em {self.project}"


class ProjectVote(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Voto de relevância"
        verbose_name_plural = "Votos de relevância"
        constraints = [models.UniqueConstraint(fields=["project", "user"], name="unique_project_vote")]


class ProjectMilestone(models.Model):
    TYPE_START = "inicio"
    TYPE_PROGRESS = "avanco"
    TYPE_PAUSE = "pausa"
    TYPE_COMPLETE = "conclusao"
    TYPE_CHOICES = ((TYPE_START, "Início"), (TYPE_PROGRESS, "Avanço"), (TYPE_PAUSE, "Pausa"), (TYPE_COMPLETE, "Conclusão"))
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_milestones")
    title = models.CharField("Título", max_length=140)
    description = models.TextField("Descrição", max_length=1000)
    milestone_type = models.CharField("Tipo", max_length=20, choices=TYPE_CHOICES, default=TYPE_PROGRESS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Marco de projeto"
        verbose_name_plural = "Marcos de projetos"
        ordering = ["-created_at"]


class CollaborationRequest(models.Model):
    PENDING = "pendente"
    ACCEPTED = "aceita"
    REJECTED = "recusada"
    STATUS_CHOICES = ((PENDING, "Pendente"), (ACCEPTED, "Aceita"), (REJECTED, "Recusada"))
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="collaboration_requests")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="collaboration_requests")
    message = models.CharField("Mensagem", max_length=500)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Solicitação de colaboração"
        verbose_name_plural = "Solicitações de colaboração"
        constraints = [models.UniqueConstraint(fields=["project", "requester"], name="unique_collaboration_request")]
        ordering = ["-created_at"]


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=40)
    message = models.CharField(max_length=280)
    url = models.CharField(max_length=300, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ["-created_at"]


class ProgramaInstitucional(models.Model):
    STATUS_RASCUNHO = "rascunho"
    STATUS_PUBLICADO = "publicado"
    STATUS_ARQUIVADO = "arquivado"
    STATUS_CHOICES = (
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_PUBLICADO, "Publicado"),
        (STATUS_ARQUIVADO, "Arquivado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacao = models.ForeignKey(
        Organizacao,
        on_delete=models.CASCADE,
        related_name="programas",
        verbose_name="Organização",
    )
    nome = models.CharField("Nome", max_length=160)
    slug = models.SlugField("Identificador", max_length=80)
    descricao = models.TextField("Descrição", max_length=1000, blank=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="programas_criados",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Programa institucional"
        verbose_name_plural = "Programas institucionais"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["organizacao", "slug"], name="unique_program_slug_per_org")
        ]

    def __str__(self):
        return self.nome


class Turma(models.Model):
    STATUS_ATIVO = "ativo"
    STATUS_ENCERRADO = "encerrado"
    STATUS_CHOICES = ((STATUS_ATIVO, "Ativa"), (STATUS_ENCERRADO, "Encerrada"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programa = models.ForeignKey(ProgramaInstitucional, on_delete=models.CASCADE, related_name="turmas", verbose_name="Programa")
    nome = models.CharField("Nome", max_length=160)
    descricao = models.TextField("Descrição", max_length=1000, blank=True)
    professor_responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="turmas_orientadas", verbose_name="Professor responsável", null=True, blank=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVO)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="turmas_criadas", verbose_name="Criado por")
    legado_id = models.UUIDField("ID legado", null=True, blank=True, unique=True, editable=False)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Turma"
        verbose_name_plural = "Turmas"
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["programa", "nome"], name="unique_class_name_per_program")]

    def __str__(self):
        return f"{self.nome} — {self.programa.nome}"


class Grupo(models.Model):
    STATUS_ATIVO = "ativo"
    STATUS_ENCERRADO = "encerrado"
    STATUS_CHOICES = ((STATUS_ATIVO, "Aberto"), (STATUS_ENCERRADO, "Encerrado"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name="grupos", verbose_name="Turma")
    nome = models.CharField("Nome", max_length=160)
    descricao = models.TextField("Descrição", max_length=1000, blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="grupos_criados", verbose_name="Criado por")
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVO)
    aberto_para_entrada = models.BooleanField("Aberto para entrada de membros", default=False)
    legado_id = models.UUIDField("ID legado", null=True, blank=True, unique=True, editable=False)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Grupo"
        verbose_name_plural = "Grupos"
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["turma", "nome"], name="unique_group_name_per_class")]

    def __str__(self):
        return f"{self.nome} — {self.turma.nome}"


class MembroTurma(models.Model):
    STATUS_ATIVO = "ativo"
    STATUS_SUSPENSO = "suspenso"
    STATUS_CHOICES = ((STATUS_ATIVO, "Ativo"), (STATUS_SUSPENSO, "Suspenso"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name="membros", verbose_name="Turma")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membros_turma", verbose_name="Usuário")
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVO)
    entrou_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membro de turma"
        verbose_name_plural = "Membros de turmas"
        constraints = [models.UniqueConstraint(fields=["turma", "usuario"], name="unique_member_per_class")]


class MembroGrupo(models.Model):
    STATUS_ATIVO = "ativo"
    STATUS_SUSPENSO = "suspenso"
    STATUS_CHOICES = ((STATUS_ATIVO, "Ativo"), (STATUS_SUSPENSO, "Suspenso"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name="membros", verbose_name="Grupo")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membros_grupo", verbose_name="Usuário")
    representante = models.BooleanField("Representante", default=False)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVO)
    entrou_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membro de grupo"
        verbose_name_plural = "Membros de grupos"
        constraints = [models.UniqueConstraint(fields=["grupo", "usuario"], name="unique_member_per_group_v2")]


class TurmaGrupo(models.Model):
    TIPO_TURMA = "turma"
    TIPO_GRUPO = "grupo"
    TIPO_CHOICES = ((TIPO_TURMA, "Turma"), (TIPO_GRUPO, "Grupo"))
    STATUS_ATIVO = "ativo"
    STATUS_ENCERRADO = "encerrado"
    STATUS_CHOICES = ((STATUS_ATIVO, "Ativo"), (STATUS_ENCERRADO, "Encerrado"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programa = models.ForeignKey(
        ProgramaInstitucional,
        on_delete=models.CASCADE,
        related_name="turmas_grupos",
        verbose_name="Programa",
    )
    nome = models.CharField("Nome", max_length=160)
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, default=TIPO_TURMA)
    descricao = models.TextField("Descrição", max_length=1000, blank=True)
    professor_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="turmas_grupos_orientados",
        verbose_name="Professor responsável",
        null=True,
        blank=True,
    )
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVO)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="turmas_grupos_criados",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Turma ou grupo"
        verbose_name_plural = "Turmas e grupos"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} — {self.programa.nome}"


class MembroTurmaGrupo(models.Model):
    PAPEL_PROFESSOR = "professor"
    PAPEL_MEMBRO = "membro"
    PAPEL_CHOICES = ((PAPEL_PROFESSOR, "Professor"), (PAPEL_MEMBRO, "Membro"))
    STATUS_ATIVO = "ativo"
    STATUS_SUSPENSO = "suspenso"
    STATUS_CHOICES = ((STATUS_ATIVO, "Ativo"), (STATUS_SUSPENSO, "Suspenso"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    turma_grupo = models.ForeignKey(
        TurmaGrupo,
        on_delete=models.CASCADE,
        related_name="membros",
        verbose_name="Turma ou grupo",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membros_turma_grupo",
        verbose_name="Usuário",
    )
    papel = models.CharField("Papel local", max_length=20, choices=PAPEL_CHOICES, default=PAPEL_MEMBRO)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVO)
    entrou_em = models.DateTimeField("Entrou em", auto_now_add=True)

    class Meta:
        verbose_name = "Membro de turma ou grupo"
        verbose_name_plural = "Membros de turmas e grupos"
        constraints = [
            models.UniqueConstraint(fields=["turma_grupo", "usuario"], name="unique_member_per_group")
        ]

    def __str__(self):
        return f"{self.usuario} — {self.turma_grupo.nome}"


class ConviteTurmaGrupo(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_ACEITO = "aceito"
    STATUS_REVOGADO = "revogado"
    STATUS_CHOICES = (
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_ACEITO, "Aceito"),
        (STATUS_REVOGADO, "Revogado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    turma_grupo = models.ForeignKey(
        TurmaGrupo,
        on_delete=models.CASCADE,
        related_name="convites",
        verbose_name="Turma ou grupo",
    )
    convidado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="convites_turma_grupo_emitidos",
        verbose_name="Convidado por",
    )
    email = models.EmailField("E-mail convidado")
    papel = models.CharField("Papel local", max_length=20, choices=MembroTurmaGrupo.PAPEL_CHOICES, default=MembroTurmaGrupo.PAPEL_MEMBRO)
    hash_token = models.CharField("Hash do token", max_length=64, unique=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    expira_em = models.DateTimeField("Expira em")
    aceito_em = models.DateTimeField("Aceito em", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Convite de turma ou grupo"
        verbose_name_plural = "Convites de turmas e grupos"
        indexes = [models.Index(fields=["turma_grupo", "status"]), models.Index(fields=["email", "status"])]

    def __str__(self):
        return f"{self.email} — {self.turma_grupo.nome}"


class ProjetoTurmaGrupo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projeto = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="vinculo_turma_grupo",
        verbose_name="Projeto",
    )
    turma_grupo = models.ForeignKey(
        TurmaGrupo,
        on_delete=models.CASCADE,
        related_name="projetos_vinculados",
        verbose_name="Turma ou grupo",
    )
    vinculado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="projetos_turma_grupo_vinculados",
        verbose_name="Vinculado por",
    )
    vinculado_em = models.DateTimeField("Vinculado em", auto_now_add=True)

    class Meta:
        verbose_name = "Vínculo de projeto a turma ou grupo"
        verbose_name_plural = "Vínculos de projetos a turmas e grupos"

    def __str__(self):
        return f"{self.projeto.title} — {self.turma_grupo.nome}"
