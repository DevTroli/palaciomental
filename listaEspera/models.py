from django.conf import settings
from django.db import models


class WaitlistEntry(models.Model):
    """Entrada na lista de espera do Palácio Mental."""
    nome = models.CharField("Nome", max_length=120)
    telefone = models.CharField("Telefone", max_length=20)
    email = models.EmailField("E-mail")
    consent = models.BooleanField("Consentimento LGPD", default=False)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Entrada na Lista de Espera"
        verbose_name_plural = "Entradas na Lista de Espera"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.nome} ({self.email})"


class MemberProfile(models.Model):
    """Informações públicas e curtas do portfólio de um membro."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    bio = models.CharField("Biografia", max_length=280, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
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
    VISIBILITY_CHOICES = ((VISIBILITY_PUBLIC, "Público"), (VISIBILITY_PRIVATE, "Privado"))

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_projects")
    title = models.CharField("Título", max_length=140)
    direction = models.TextField("Direção", max_length=1000, help_text="Por que este projeto existe?")
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_IDEA)
    visibility = models.CharField("Visibilidade", max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE)
    category = models.CharField("Categoria", max_length=80)
    tags = models.CharField("Tags", max_length=300, blank=True, help_text="Separe as tags por vírgula")
    seeking_collaborators = models.BooleanField("Buscando colaboradores", default=False)
    collaboration_description = models.CharField("O que procura", max_length=280, blank=True)
    collaboration_tags = models.CharField("Tags de colaboração", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["visibility", "status", "category"])]

    def tag_list(self):
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    def __str__(self):
        return self.title


class ProjectMember(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships")
    role = models.CharField("Papel", max_length=80, default="Colaborador")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
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
        ordering = ["created_at"]

    def __str__(self):
        return f"Comentário de {self.author} em {self.project}"


class ProjectVote(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
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
        ordering = ["-created_at"]
