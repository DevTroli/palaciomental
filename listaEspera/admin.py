from django.contrib import admin
from .models import WaitlistEntry


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "telefone", "consent", "created_at")
    list_filter = ("consent", "created_at")
    search_fields = ("nome", "email", "telefone")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
