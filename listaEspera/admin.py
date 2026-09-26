from django.contrib import admin
from .models import CollaborationRequest, Notification, ProjectComment, ProjectMilestone, ProjectVote, WaitlistEntry


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "telefone", "consent", "created_at")
    list_filter = ("consent", "created_at")
    search_fields = ("nome", "email", "telefone")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


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
