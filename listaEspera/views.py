from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import WaitlistEntry


def index(request):
    return render(request, "listaEspera/index.html")


def saude(request):
    return JsonResponse({"status": "ok"})


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
