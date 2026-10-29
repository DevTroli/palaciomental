from django.shortcuts import render

from plataforma.models import Project


def index(request):
    """Homepage institucional e porta de entrada do produto."""
    latest_projects = Project.objects.filter(
        visibility=Project.VISIBILITY_PUBLIC,
        organizacao__isnull=True,
    ).select_related("owner")[:3]
    return render(request, "core/index.html", {"latest_projects": latest_projects})
