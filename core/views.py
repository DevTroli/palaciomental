from django.shortcuts import redirect, render

from listaEspera.models import Project


def index(request):
    """Homepage institucional e porta de entrada do produto."""
    latest_projects = Project.objects.filter(visibility=Project.VISIBILITY_PUBLIC).select_related("owner")[:3]
    return render(request, "core/index.html", {"latest_projects": latest_projects})


def mvp_redirect(request):
    """Mantém links antigos funcionais depois da promoção do MVP para /."""
    return redirect("core:index", permanent=True)
