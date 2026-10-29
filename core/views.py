from django.shortcuts import redirect, render

from plataforma.models import Project


def index(request):
    """Homepage institucional e porta de entrada do produto."""
    if getattr(request, "organizacao", None) is not None and getattr(request, "membro_organizacao", None) is not None:
        return redirect("plataforma:institutional_management")
    latest_projects = Project.objects.filter(
        visibility=Project.VISIBILITY_PUBLIC,
        organizacao__isnull=True,
    ).select_related("owner")[:3]
    return render(request, "core/index.html", {"latest_projects": latest_projects})
