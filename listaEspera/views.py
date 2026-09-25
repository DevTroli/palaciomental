import json
import os
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import DatabaseError
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .forms import MemberCreationForm, ProfileForm, ProjectForm
from .models import MemberProfile, Project, ProjectMember, WaitlistEntry

def register(request):
    if request.user.is_authenticated:
        return redirect("listaEspera:profile", username=request.user.username)
    form = MemberCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        MemberProfile.objects.create(user=user)
        login(request, user)
        messages.success(request, "Conta criada. Agora você pode dar forma ao seu primeiro projeto.")
        return redirect("listaEspera:profile", username=user.username)
    return render(request, "auth/register.html", {"form": form})


def login_view(request):
    from django.contrib.auth.forms import AuthenticationForm
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next") or "listaEspera:projects")
    return render(request, "auth/login.html", {"form": form})


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect("core:index")


def profile(request, username):
    user = get_object_or_404(User, username=username)
    MemberProfile.objects.get_or_create(user=user)
    owned = user.owned_projects.filter(visibility=Project.VISIBILITY_PUBLIC)
    collaborated = Project.objects.filter(memberships__user=user, visibility=Project.VISIBILITY_PUBLIC).exclude(owner=user).distinct()
    return render(request, "members/profile.html", {"member": user, "owned_projects": owned, "collaborated_projects": collaborated})


@login_required
def profile_edit(request):
    profile_obj, _ = MemberProfile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile_obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Seu perfil foi atualizado.")
        return redirect("listaEspera:profile", username=request.user.username)
    return render(request, "members/profile_edit.html", {"form": form})


def projects(request):
    queryset = Project.objects.filter(visibility=Project.VISIBILITY_PUBLIC).select_related("owner")
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    status = request.GET.get("status", "").strip()
    tag = request.GET.get("tag", "").strip()
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(direction__icontains=query))
    if category:
        queryset = queryset.filter(category__iexact=category)
    if status:
        queryset = queryset.filter(status=status)
    if tag:
        queryset = queryset.filter(tags__icontains=tag)
    categories = Project.objects.filter(visibility=Project.VISIBILITY_PUBLIC).values_list("category", flat=True).distinct().order_by("category")
    context = {"projects": queryset, "categories": categories, "statuses": Project.STATUS_CHOICES, "filters": {"q": query, "category": category, "status": status, "tag": tag}}
    return render(request, "projects/list.html", context)


def project_detail(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)
    if project.visibility == Project.VISIBILITY_PRIVATE and project.owner != request.user and not project.memberships.filter(user=request.user).exists():
        raise Http404
    return render(request, "projects/detail.html", {"project": project, "members": project.memberships.select_related("user")})


@login_required
def project_create(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        messages.success(request, "Projeto criado. Agora você pode acompanhar sua evolução.")
        return redirect("listaEspera:project_detail", pk=project.pk)
    return render(request, "projects/form.html", {"form": form, "heading": "Criar projeto", "submit_label": "Criar projeto"})


@login_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Projeto atualizado.")
        return redirect("listaEspera:project_detail", pk=project.pk)
    return render(request, "projects/form.html", {"form": form, "heading": "Editar projeto", "submit_label": "Salvar alterações", "project": project})


def saude(request):
    deployment = {
        label: value
        for label, value in {
            "commit": os.getenv("RAILWAY_GIT_COMMIT_SHA"),
            "author": os.getenv("RAILWAY_GIT_AUTHOR"),
            "branch": os.getenv("RAILWAY_GIT_BRANCH"),
            "service": os.getenv("RAILWAY_SERVICE_NAME"),
            "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME"),
        }.items()
        if value
    }
    return JsonResponse({"status": "ok", "deployment": deployment})


STATUS_COPY = {
    "operacional": ("operational", "Funcionando", "Tudo funcionando normalmente.", "✓"),
    "degradado": ("degraded", "Instabilidade", "Pode haver alguma lentidão ou falha pontual.", "!"),
    "indisponivel": ("unavailable", "Indisponível", "Este serviço não está disponível agora.", "×"),
}


def _service_status(raw_status):
    """Converte o status técnico da API em dados seguros e amigáveis para a UI."""
    normalized = str(raw_status or "").strip().lower()
    return STATUS_COPY.get(
        normalized,
        ("unknown", "Não verificado", "Não foi possível verificar este serviço agora.", "?"),
    )


def _fetch_status_api():
    """Busca o payload da status_api sem deixar uma falha externa quebrar a página."""
    request = Request(
        settings.STATUS_API_URL,
        headers={"Accept": "application/json", "User-Agent": "PalacioMentalStatus/1.0"},
    )
    with urlopen(request, timeout=settings.STATUS_API_TIMEOUT) as response:
        if response.status < 200 or response.status >= 300:
            return None
        payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None


def _service_card(name, icon, raw_status, metrics=None, group="Serviços principais"):
    status, label, message, _ = _service_status(raw_status)
    return {
        "name": name,
        "icon": icon,
        "status": status,
        "label": label,
        "message": message,
        "metrics": metrics or [],
        "group": group,
    }


def _database_metrics(database):
    details = database.get("details") or {}
    metrics = []
    if details.get("version"):
        metrics.append({"label": "Versão", "value": str(details["version"]).split()[0]})
    if details.get("used_connections") is not None:
        metrics.append({"label": "Conexões em uso", "value": details["used_connections"]})
    if details.get("max_connections") is not None:
        metrics.append({"label": "Limite de conexões", "value": details["max_connections"]})
    if database.get("response_time_ms") is not None:
        metrics.append({"label": "Resposta", "value": f"{database['response_time_ms']} ms"})
    return metrics


def _response_metric(service):
    if service.get("response_time_ms") is None:
        return []
    return [{"label": "Resposta", "value": f"{service['response_time_ms']} ms"}]


def _deployment_metrics(deployment):
    labels = {
        "commit": "Commit",
        "author": "Autor",
        "branch": "Branch",
        "service": "Serviço",
        "environment": "Ambiente",
    }
    return [
        {"label": labels[key], "value": value[:12] if key == "commit" else value}
        for key, value in deployment.items()
        if key in labels and value
    ]


def _waitlist_analytics():
    """Prepara apenas dados agregados e públicos para a seção de tração."""
    try:
        now = datetime.now().astimezone()
        first_signup = WaitlistEntry.objects.order_by("created_at").values_list("created_at", flat=True).first()
        total = WaitlistEntry.objects.count()
        if not first_signup:
            return {"total": 0, "first_signup": None, "points": [], "polyline": "", "chart_max": 1, "has_data": False}
        first_date = first_signup.astimezone().date()
        daily_rows = list(
            WaitlistEntry.objects.filter(created_at__date__gte=first_date)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"))
            .order_by("day")
        )
        daily_totals = {row["day"]: row["total"] for row in daily_rows}
    except DatabaseError:
        return {"total": None, "first_signup": None, "points": [], "polyline": "", "chart_max": 1, "has_data": False}
    cumulative = 0
    points = []
    width, height = 720, 220
    left, right, top, bottom = 42, 12, 18, 34
    chart_width = width - left - right
    chart_height = height - top - bottom
    dates = []
    cursor = first_date
    while cursor <= now.date():
        dates.append(cursor)
        cursor += timedelta(days=1)
    chart_max = max(total, 1)
    for index, current_date in enumerate(dates):
        cumulative += daily_totals.get(current_date, 0)
        x = left if len(dates) == 1 else left + (chart_width * index / (len(dates) - 1))
        y = top + chart_height - (chart_height * cumulative / chart_max)
        points.append({
            "x": round(x, 2),
            "y": round(y, 2),
            "value": cumulative,
            "label": current_date.strftime("%d/%m"),
        })
    return {
        "total": total,
        "first_signup": first_signup.astimezone().strftime("%d/%m/%Y"),
        "points": points,
        "polyline": " ".join(f"{point['x']},{point['y']}" for point in points),
        "chart_max": chart_max,
        "has_data": bool(points),
    }


def status_page(request):
    """Exibe o estado resumido dos serviços sem depender da disponibilidade da API."""
    context = {"status_available": False, "services": [], "analytics": _waitlist_analytics()}
    try:
        payload = _fetch_status_api()
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        payload = None

    if payload:
        dependencies = payload.get("dependencies") or {}
        database = dependencies.get("database") or {}
        django = dependencies.get("django_app") or {}
        deployment = payload.get("deployment") or django.get("deployment") or {}
        context.update(
            status_available=True,
            overall_status=_service_status(payload.get("status"))[0],
            overall_label=_service_status(payload.get("status"))[1],
            overall_message=_service_status(payload.get("status"))[2],
            overall_icon=_service_status(payload.get("status"))[3],
            services=[
                _service_card(
                    "Banco de dados", "▦", database.get("status"), _database_metrics(database), "Banco de dados"
                ),
                _service_card(
                    "Aplicação web (Django)",
                    "⌂",
                    django.get("status"),
                    _response_metric(django) + ([{"label": "Verificação", "value": "GET /saude"}] if django else []),
                    "Servidor web",
                ),
                _service_card(
                    "API de status", "↗", payload.get("status"), _response_metric(payload), "APIs e serviços"
                ),
            ],
            deployment_metrics=_deployment_metrics(deployment),
        )
        checked_at = payload.get("checked_at")
        if checked_at:
            try:
                context["checked_at"] = datetime.fromisoformat(checked_at.replace("Z", "+00:00")).strftime(
                    "%d/%m/%Y às %H:%M"
                )
            except (TypeError, ValueError):
                pass
    else:
        context["services"] = [
            _service_card("Banco de dados", "▦", None),
            _service_card("Aplicação web", "⌂", None),
            _service_card("API de status", "↗", None),
        ]

    return render(request, "status.html", context)


@require_http_methods(["POST"])
def waitlist_submit(request):
    """Recebe submissão do formulário de lista de espera e salva no banco."""
    nome = request.POST.get("nome", "").strip()
    telefone = request.POST.get("telefone", "").strip()
    email = request.POST.get("email", "").strip().lower()
    consent = request.POST.get("consent") == "on"

    # Validação básica
    if not all([nome, telefone, email]):
        return JsonResponse(
            {"success": False, "error": "Todos os campos são obrigatórios"},
            status=400
        )

    if not consent:
        return JsonResponse(
            {"success": False, "error": "Consentimento LGPD é obrigatório"},
            status=400
        )

    # Evita duplicata por email
    if WaitlistEntry.objects.filter(email=email).exists():
        return JsonResponse(
            {"success": False, "error": "Este e-mail já está cadastrado"},
            status=400
        )

    WaitlistEntry.objects.create(
        nome=nome,
        telefone=telefone,
        email=email,
        consent=consent
    )

    return JsonResponse({"success": True})
