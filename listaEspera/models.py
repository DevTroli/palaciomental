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
