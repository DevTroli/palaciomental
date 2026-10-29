from django.contrib import admin
from .models import (
    CollaborationRequest,
    ConviteOrganizacao,
    DominioOrganizacao,
    IdentidadeOrganizacao,
    MembroOrganizacao,
    Notification,
    Organizacao,
    ProjectComment,
    ProjectMilestone,
    ProjectVote,
)


@admin.register(Organizacao)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "status", "atualizado_em")
    list_filter = ("status",)
    search_fields = ("nome", "slug", "nome_legal")


@admin.register(IdentidadeOrganizacao)
class IdentidadeOrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("organizacao", "nome_exibicao", "cor_primaria", "cor_fundo")
    search_fields = ("organizacao__nome", "nome_exibicao")


@admin.register(DominioOrganizacao)
class DominioOrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("hostname", "organizacao", "tipo", "principal", "status_verificacao")
    list_filter = ("tipo", "principal", "status_verificacao")
    search_fields = ("hostname", "organizacao__nome")


@admin.register(MembroOrganizacao)
class MembroOrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "organizacao", "papel", "status", "entrou_em")
    list_filter = ("papel", "status")
    search_fields = ("usuario__username", "usuario__email", "organizacao__nome")


@admin.register(ConviteOrganizacao)
class ConviteOrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("email", "organizacao", "papel", "status", "expira_em")
    list_filter = ("papel", "status")
    search_fields = ("email", "organizacao__nome")
    readonly_fields = ("hash_token", "criado_em", "aceito_em")


@admin.register(ProjectComment)
class ProjectCommentAdmin(admin.ModelAdmin):
    list_display = ("project", "author", "created_at")
    search_fields = ("content", "project__title", "author__username")


@admin.register(ProjectMilestone)
class ProjectMilestoneAdmin(admin.ModelAdmin):
    list_display = ("project", "title", "milestone_type", "author", "created_at")
    list_filter = ("milestone_type",)


@admin.register(ProjectVote)
class ProjectVoteAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "created_at")


@admin.register(CollaborationRequest)
class CollaborationRequestAdmin(admin.ModelAdmin):
    list_display = ("project", "requester", "status", "created_at")
    list_filter = ("status",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "kind", "read_at", "created_at")
    list_filter = ("kind", "read_at")
