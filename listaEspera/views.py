import json
from datetime import datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import WaitlistEntry


def index(request):
    return render(request, "listaEspera/index.html")


def saude(request):
    return JsonResponse({"status": "ok"})


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


def status_page(request):
    """Exibe o estado resumido dos serviços sem depender da disponibilidade da API."""
    context = {"status_available": False, "services": []}
    try:
        payload = _fetch_status_api()
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        payload = None

    if payload:
        dependencies = payload.get("dependencies") or {}
        database = dependencies.get("database") or {}
        django = dependencies.get("django_app") or {}
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
                    "Aplicação web", "⌂", django.get("status"), _response_metric(django), "Servidor web"
                ),
                _service_card(
                    "API de status", "↗", payload.get("status"), _response_metric(payload), "APIs e serviços"
                ),
            ],
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
