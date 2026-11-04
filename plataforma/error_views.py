"""Erros de acesso sem detalhes técnicos, tokens ou dados submetidos."""

import logging

from django.shortcuts import render
from django.urls import Resolver404, resolve, reverse
from django.views.decorators.cache import never_cache

logger = logging.getLogger(__name__)


def _recovery_url(request):
    try:
        match = resolve(request.path)
    except Resolver404:
        return ""
    allowed = {
        "plataforma:institutional_invite_accept",
        "plataforma:institutional_organization_invite_accept",
        "plataforma:login",
        "plataforma:register",
    }
    if match.view_name not in allowed:
        return ""
    return reverse(match.view_name, kwargs=match.kwargs)


@never_cache
def csrf_failure(request, reason=""):
    # Não registrar reason completo: pode conter valores de headers controlados
    # pelo cliente. Nunca incluir caminho/token, corpo POST ou e-mail no log.
    category = "token"
    if "Referer" in reason:
        category = "referer"
    elif "Origin" in reason:
        category = "origin"
    logger.warning("Envio bloqueado por CSRF; categoria=%s", category)
    response = render(request, "errors/403.html", {
        "error_title": "Não foi possível validar este envio",
        "error_message": (
            "Por segurança, o envio foi interrompido. Reabra o formulário e tente "
            "novamente. Se o problema continuar, procure a gestão do ambiente."
        ),
        "recovery_url": _recovery_url(request),
        "recovery_label": "Reabrir formulário",
    }, status=403)
    response["Referrer-Policy"] = "strict-origin"
    return response


@never_cache
def permission_denied(request, exception):
    response = render(request, "errors/403.html", {
        "error_title": "Este acesso não está disponível",
        "error_message": (
            "Sua conta pode não ter permissão, ou o convite pode ter expirado ou "
            "já ter sido utilizado. Confira se está na conta e no ambiente corretos. "
            "Se precisar, solicite um novo convite à gestão."
        ),
    }, status=403)
    response["Referrer-Policy"] = "strict-origin"
    return response
