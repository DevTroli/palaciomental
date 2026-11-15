"""Consulta somente IDs previamente autorizados pelo Django."""

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from django.core.management.base import CommandError
from django.utils.dateparse import parse_datetime

from .management.commands.enviar_links_guardiao import Command, _NoRedirect
from .models import GuardiaoLinkPendente, ProjectLink

logger = logging.getLogger(__name__)

ROTULOS = {
    "ACESSIVEL": "Disponível",
    "REDIRECIONADO": "Redireciona",
    "REQUER_LOGIN": "Requer acesso",
    "QUEBRADO": "Link quebrado",
    "SEM_RESPOSTA": "Sem resposta",
}


def consultar_links(links):
    """Retorna None se o serviço estiver indisponível, ou resultados por ID."""
    ids = list(dict.fromkeys(link.pk for link in links))
    if not ids:
        return {}
    pending = set(GuardiaoLinkPendente.objects.filter(pk__in=ids).values_list("pk", flat=True))
    try:
        endpoint, token = Command()._configuracao()
        opener = build_opener(_NoRedirect())
        results = {}
        for start in range(0, len(ids), 100):
            chunk = ids[start:start + 100]
            request = Request(endpoint + "/results", method="POST", data=json.dumps({"link_ids": chunk}).encode(),
                              headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            with opener.open(request, timeout=2) as response:  # nosec B310: destino validado na configuração
                data = json.loads(response.read(65537))
            if not isinstance(data, list) or len(data) > len(chunk):
                raise ValueError("Resposta inválida")
            for item in data:
                link_id = item["link_id"]
                status = item["status"]
                checked_at = parse_datetime(item["checked_at"]) if item["checked_at"] else None
                if link_id not in chunk or (status is not None and status not in ROTULOS):
                    raise ValueError("Resposta inválida")
                if link_id not in pending and status and checked_at:
                    label = ROTULOS[status]
                    if status == "QUEBRADO" and item.get("failed_cycles", 0) < 3:
                        label = "Possível quebra"
                    results[link_id] = {"status": status, "label": label, "checked_at": checked_at}
        # Uma edição pode ter sido enfileirada enquanto o serviço respondia.
        pending.update(GuardiaoLinkPendente.objects.filter(pk__in=ids).values_list("pk", flat=True))
        return {pk: value for pk, value in results.items() if pk not in pending}
    except HTTPError as exc:
        logger.warning("Consulta ao Guardião falhou com HTTP %s.", exc.code)
        return None
    except (CommandError, URLError, OSError, TimeoutError, ValueError, TypeError, KeyError, AttributeError) as exc:
        logger.warning("Consulta ao Guardião indisponível (%s).", type(exc).__name__)
        return None


def marcar_links(links):
    results = consultar_links(links)
    for link in links:
        link.guardiao = (results or {}).get(link.pk)
        link.guardiao_indisponivel = results is None
    return links


def contar_atencao(user, organizacao):
    # Somente projetos do autor, no ambiente atual. IDs nunca vêm do navegador.
    links = list(ProjectLink.objects.filter(project__owner=user, project__organizacao=organizacao).only("id"))
    results = consultar_links(links)
    if results is None:
        return None
    return sum(item["status"] in {"QUEBRADO", "SEM_RESPOSTA"} for item in results.values())
