import secrets

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError

from .models import (
    CollaborationRequest,
    ConviteOrganizacao,
    ConviteTurmaGrupo,
    DominioOrganizacao,
    IdentidadeOrganizacao,
    MemberProfile,
    MembroOrganizacao,
    Notification,
    Organizacao,
    MembroTurmaGrupo,
    ProgramaInstitucional,
    ProjetoTurmaGrupo,
    Project,
    ProjectComment,
    ProjectLink,
    ProjectMember,
    ProjectMilestone,
    ProjectVote,
    TurmaGrupo,
)
from .services import ativar_organizacao


User = get_user_model()


class DominioOrganizacaoForm(forms.ModelForm):
    class Meta:
        model = DominioOrganizacao
        fields = "__all__"

    def clean_hostname(self):
        hostname = self.cleaned_data["hostname"].strip().lower().rstrip(".")
        if " " in hostname or "/" in hostname:
            raise forms.ValidationError("Informe apenas o hostname, sem espaços, barras ou protocolo.")
        if hostname.startswith(("http://", "https://")):
            raise forms.ValidationError("Informe somente o hostname, sem http:// ou https://.")
        return hostname


class IdentidadeOrganizacaoInline(admin.StackedInline):
    model = IdentidadeOrganizacao
    extra = 0
    max_num = 1
    fieldsets = (
        ("Identidade exibida", {"fields": ("nome_exibicao", "logo")}),
        ("Cores da organização", {"fields": ("cor_primaria", "cor_destaque", "cor_fundo")} ),
    )


class DominioOrganizacaoInline(admin.TabularInline):
    model = DominioOrganizacao
    form = DominioOrganizacaoForm
    extra = 0
    fields = ("hostname", "tipo", "principal", "status_verificacao", "verificado_em")
    readonly_fields = ("verificado_em",)


@admin.action(description="Ativar organizações selecionadas")
def ativar_organizacoes(modeladmin, request, queryset):
    ativadas = 0
    for organizacao in queryset:
        try:
            ativar_organizacao(organizacao, executor=request.user)
            ativadas += 1
        except ValidationError as exc:
            modeladmin.message_user(request, f"{organizacao.nome}: {exc.message}", level=messages.ERROR)
    if ativadas:
        modeladmin.message_user(request, f"{ativadas} organização(ões) ativada(s).", level=messages.SUCCESS)


@admin.action(description="Suspender organizações selecionadas")
def suspender_organizacoes(modeladmin, request, queryset):
    queryset.update(status=Organizacao.STATUS_SUSPENSA)


@admin.register(Organizacao)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "status_legivel", "quantidade_dominios", "quantidade_membros", "atualizado_em")
    list_display_links = ("nome",)
    list_filter = ("status",)
    search_fields = ("nome", "nome_legal", "slug")
    ordering = ("nome",)
    date_hierarchy = "atualizado_em"
    readonly_fields = ("id", "criado_em", "atualizado_em")
    actions = (ativar_organizacoes, suspender_organizacoes)
    inlines = (IdentidadeOrganizacaoInline, DominioOrganizacaoInline)
    fieldsets = (
        ("Identificação da organização", {"fields": ("nome", "nome_legal", "slug")} ),
        ("Disponibilidade do ambiente", {"fields": ("status",)}),
        ("Auditoria", {"fields": ("id", "criado_em", "atualizado_em"), "classes": ("collapse",)}),
    )

    @admin.display(description="Situação", ordering="status")
    def status_legivel(self, obj):
        return obj.get_status_display()

    @admin.display(description="Domínios")
    def quantidade_dominios(self, obj):
        return obj.dominios.count()

    @admin.display(description="Membros")
    def quantidade_membros(self, obj):
        return obj.afiliacoes.count()


@admin.register(DominioOrganizacao)
class DominioOrganizacaoAdmin(admin.ModelAdmin):
    form = DominioOrganizacaoForm
    list_display = ("hostname", "organizacao", "tipo_legivel", "principal", "status_verificacao")
    list_filter = ("tipo", "principal", "status_verificacao", "organizacao__status")
    search_fields = ("hostname", "organizacao__nome", "organizacao__slug")
    list_select_related = ("organizacao",)
    autocomplete_fields = ("organizacao",)
    readonly_fields = ("id", "verificado_em")
    fieldsets = (
        ("Roteamento do ambiente", {"fields": ("organizacao", "hostname", "tipo", "principal")} ),
        ("Verificação", {"fields": ("status_verificacao", "verificado_em")} ),
        ("Identificador técnico", {"fields": ("id",), "classes": ("collapse",)}),
    )

    @admin.display(description="Tipo", ordering="tipo")
    def tipo_legivel(self, obj):
        return obj.get_tipo_display()


@admin.register(IdentidadeOrganizacao)
class IdentidadeOrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("organizacao", "nome_exibicao", "cor_primaria", "cor_destaque", "cor_fundo")
    search_fields = ("organizacao__nome", "organizacao__slug", "nome_exibicao")
    list_select_related = ("organizacao",)
    autocomplete_fields = ("organizacao",)
    fieldsets = (
        ("Organização", {"fields": ("organizacao", "nome_exibicao", "logo")} ),
        ("Cores", {"fields": ("cor_primaria", "cor_destaque", "cor_fundo")} ),
    )


@admin.register(MembroOrganizacao)
class MembroOrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "organizacao", "papel_legivel", "status_legivel", "entrou_em")
    list_filter = ("papel", "status", "organizacao__status")
    search_fields = ("usuario__username", "usuario__email", "usuario__first_name", "usuario__last_name", "organizacao__nome")
    list_select_related = ("usuario", "organizacao")
    autocomplete_fields = ("organizacao", "usuario")
    readonly_fields = ("id", "entrou_em")
    fieldsets = (
        ("Vínculo institucional", {"fields": ("organizacao", "usuario", "papel", "status")} ),
        ("Auditoria", {"fields": ("id", "entrou_em"), "classes": ("collapse",)}),
    )

    @admin.display(description="Papel", ordering="papel")
    def papel_legivel(self, obj):
        return obj.get_papel_display()

    @admin.display(description="Situação", ordering="status")
    def status_legivel(self, obj):
        return obj.get_status_display()


@admin.register(ConviteOrganizacao)
class ConviteOrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("email", "organizacao", "papel_legivel", "status_legivel", "expira_em", "criado_em")
    list_filter = ("papel", "status", "organizacao__status")
    search_fields = ("email", "organizacao__nome", "organizacao__slug")
    list_select_related = ("organizacao", "convidado_por")
    autocomplete_fields = ("organizacao", "convidado_por")
    readonly_fields = ("id", "hash_token", "convidado_por", "aceito_em", "criado_em")
    fieldsets = (
        ("Destinatário e ambiente", {"fields": ("organizacao", "email", "papel", "convidado_por")} ),
        ("Estado do convite", {"fields": ("status", "expira_em", "aceito_em")} ),
        ("Dados técnicos", {"fields": ("id", "hash_token", "criado_em"), "classes": ("collapse",)}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.hash_token:
            obj.hash_token = secrets.token_hex(32)
        if not obj.convidado_por_id and request.user.is_authenticated:
            obj.convidado_por = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Papel", ordering="papel")
    def papel_legivel(self, obj):
        return obj.get_papel_display()

    @admin.display(description="Situação", ordering="status")
    def status_legivel(self, obj):
        return obj.get_status_display()


class ProjetoAdmin(admin.ModelAdmin):
    list_display = ("title", "organizacao", "owner", "status_legivel", "visibility_legivel", "updated_at")
    list_filter = ("status", "visibility", "organizacao", "seeking_collaborators")
    search_fields = ("title", "category", "owner__username", "owner__email", "organizacao__nome")
    list_select_related = ("owner", "organizacao")
    autocomplete_fields = ("owner", "organizacao")
    readonly_fields = ("id", "access_token", "created_at", "updated_at")
    date_hierarchy = "updated_at"
    fieldsets = (
        ("Identificação", {"fields": ("title", "category", "tags")} ),
        ("Escopo e acesso", {"fields": ("owner", "organizacao", "visibility", "access_token")} ),
        ("Conteúdo", {"fields": ("direction", "status")} ),
        ("Colaboração", {"fields": ("seeking_collaborators", "collaboration_description")} ),
        ("Auditoria", {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Status", ordering="status")
    def status_legivel(self, obj):
        return obj.get_status_display()

    @admin.display(description="Visibilidade", ordering="visibility")
    def visibility_legivel(self, obj):
        return obj.get_visibility_display()


admin.site.register(Project, ProjetoAdmin)


@admin.register(ProjectLink)
class ProjectLinkAdmin(admin.ModelAdmin):
    list_display = ("label", "project", "url", "created_at")
    search_fields = ("label", "url", "project__title")
    list_select_related = ("project",)
    autocomplete_fields = ("project",)
    readonly_fields = ("id", "created_at")


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "role", "can_manage_milestones", "joined_at")
    list_filter = ("can_manage_milestones",)
    search_fields = ("project__title", "user__username", "user__email")
    list_select_related = ("project", "user")
    autocomplete_fields = ("project", "user")
    readonly_fields = ("id", "joined_at")


@admin.register(ProjectComment)
class ProjectCommentAdmin(admin.ModelAdmin):
    list_display = ("project", "author", "parent", "created_at", "updated_at")
    search_fields = ("content", "project__title", "author__username")
    list_select_related = ("project", "author", "parent")
    autocomplete_fields = ("project", "author", "parent")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ProjectMilestone)
class ProjectMilestoneAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "milestone_type", "author", "created_at")
    list_filter = ("milestone_type",)
    search_fields = ("title", "description", "project__title", "author__username")
    list_select_related = ("project", "author")
    autocomplete_fields = ("project", "author")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ProjectVote)
class ProjectVoteAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "created_at")
    search_fields = ("project__title", "user__username", "user__email")
    list_select_related = ("project", "user")
    autocomplete_fields = ("project", "user")
    readonly_fields = ("id", "created_at")


@admin.register(CollaborationRequest)
class CollaborationRequestAdmin(admin.ModelAdmin):
    list_display = ("project", "requester", "status", "created_at", "decided_at")
    list_filter = ("status",)
    search_fields = ("message", "project__title", "requester__username", "requester__email")
    list_select_related = ("project", "requester")
    autocomplete_fields = ("project", "requester")
    readonly_fields = ("id", "created_at", "decided_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "kind", "read_at", "created_at")
    list_filter = ("kind", "read_at")
    search_fields = ("recipient__username", "recipient__email", "message")
    list_select_related = ("recipient",)
    autocomplete_fields = ("recipient",)
    readonly_fields = ("id", "created_at")


@admin.register(ProgramaInstitucional)
class ProgramaInstitucionalAdmin(admin.ModelAdmin):
    list_display = ("nome", "organizacao", "status", "criado_por", "atualizado_em")
    list_filter = ("status", "organizacao__status")
    search_fields = ("nome", "slug", "organizacao__nome", "criado_por__username")
    list_select_related = ("organizacao", "criado_por")
    autocomplete_fields = ("organizacao", "criado_por")
    readonly_fields = ("id", "criado_em", "atualizado_em")


@admin.register(TurmaGrupo)
class TurmaGrupoAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "programa", "professor_responsavel", "status", "atualizado_em")
    list_filter = ("tipo", "status", "programa__organizacao")
    search_fields = ("nome", "programa__nome", "programa__organizacao__nome", "professor_responsavel__username")
    list_select_related = ("programa", "programa__organizacao", "professor_responsavel")
    autocomplete_fields = ("programa", "professor_responsavel", "criado_por")
    readonly_fields = ("id", "criado_em", "atualizado_em")


@admin.register(MembroTurmaGrupo)
class MembroTurmaGrupoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "turma_grupo", "papel", "status", "entrou_em")
    list_filter = ("papel", "status", "turma_grupo__programa__organizacao")
    search_fields = ("usuario__username", "usuario__email", "turma_grupo__nome", "turma_grupo__programa__nome")
    list_select_related = ("usuario", "turma_grupo", "turma_grupo__programa")
    autocomplete_fields = ("usuario", "turma_grupo")
    readonly_fields = ("id", "entrou_em")


@admin.register(ConviteTurmaGrupo)
class ConviteTurmaGrupoAdmin(admin.ModelAdmin):
    list_display = ("email", "turma_grupo", "papel", "status", "expira_em", "aceito_em")
    list_filter = ("status", "papel", "turma_grupo__programa__organizacao")
    search_fields = ("email", "turma_grupo__nome", "turma_grupo__programa__nome")
    list_select_related = ("turma_grupo", "turma_grupo__programa", "convidado_por")
    autocomplete_fields = ("turma_grupo", "convidado_por")
    readonly_fields = ("id", "hash_token", "criado_em", "aceito_em")


@admin.register(ProjetoTurmaGrupo)
class ProjetoTurmaGrupoAdmin(admin.ModelAdmin):
    list_display = ("projeto", "turma_grupo", "vinculado_por", "vinculado_em")
    list_filter = ("turma_grupo__programa__organizacao",)
    search_fields = ("projeto__title", "turma_grupo__nome", "turma_grupo__programa__nome")
    list_select_related = ("projeto", "turma_grupo", "turma_grupo__programa", "vinculado_por")
    autocomplete_fields = ("projeto", "turma_grupo", "vinculado_por")
    readonly_fields = ("id", "vinculado_em")


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "bio_resumida", "created_at", "updated_at")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name", "bio")
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    readonly_fields = ("id", "created_at", "updated_at")

    @admin.display(description="Biografia")
    def bio_resumida(self, obj):
        return obj.bio[:80] + ("…" if len(obj.bio) > 80 else "")


admin.site.site_header = "Palácio Mental — Operação da Plataforma"
admin.site.site_title = "Palácio Mental Admin"
admin.site.index_title = "Gestão da plataforma"
