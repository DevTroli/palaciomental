"""Consulta somente IDs previamente autorizados pelo Django."""

import json
import logging
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from django.core.management.base import CommandError
from django.utils import timezone
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


def consultar_ameacas_detalhes(urls):
    """Consulta a API interna; falhas nunca equivalem a links seguros."""
    fallback = [{"state": "UNVERIFIED", "checked_at": None, "expires_at": None}] * len(urls)
    if not urls:
        return []
    try:
        endpoint, token = Command()._configuracao()
        request = Request(endpoint + "/threats", method="POST", data=json.dumps({"urls": urls}).encode(),
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with build_opener(_NoRedirect()).open(request, timeout=10) as response:  # nosec B310: configuração validada
            results = json.loads(response.read(4097))
        if not isinstance(results, list) or len(results) != len(urls):
            return fallback
        now = timezone.now()
        validated = []
        for item in results:
            if not isinstance(item, dict) or item.get("state") not in {"THREAT", "NO_MATCH", "UNVERIFIED"}:
                return fallback
            state = item["state"]
            checked = parse_datetime(item.get("checkedAt") or "")
            expires = parse_datetime(item.get("expiresAt") or "")
            if (state != "UNVERIFIED" and (not checked or not expires or timezone.is_naive(checked)
                    or timezone.is_naive(expires) or checked > now or expires <= now
                    or (state == "THREAT" and now - checked >= timedelta(minutes=30)))):
                state, checked, expires = "UNVERIFIED", None, None
            validated.append({"state": state, "checked_at": checked, "expires_at": expires})
        return validated
    except (CommandError, HTTPError, URLError, OSError, TimeoutError, ValueError, TypeError, AttributeError):
        return fallback


def consultar_ameacas(urls):
    return [result["state"] for result in consultar_ameacas_detalhes(urls)]


def verificar_ameacas_formulario(formset):
    """Valida somente links novos ou com endereço alterado; não expõe URLs no log."""
    forms = [form for form in formset.forms
             if form.cleaned_data and not form.cleaned_data.get("DELETE")
             and form.cleaned_data.get("url") and (not form.instance.pk or "url" in form.changed_data)]
    if not forms:
        return False
    resultados = consultar_ameacas([form.cleaned_data["url"] for form in forms])
    if len(resultados) != len(forms) or any(item not in {"THREAT", "NO_MATCH", "UNVERIFIED"} for item in resultados):
        resultados = ["UNVERIFIED"] * len(forms)
    for form, resultado in zip(forms, resultados):
        if resultado == "THREAT":
            form.add_error("url", "Este link pode representar uma ameaça e não pode ser salvo. Aviso do Google Safe Browsing; a verificação pode falhar.")
    return "UNVERIFIED" in resultados


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
                    tone = "neutral"
                    if status == "ACESSIVEL":
                        tone = "success"
                    elif status == "SEM_RESPOSTA":
                        tone = "warning"
                    if status == "QUEBRADO" and item.get("failed_cycles", 0) < 3:
                        label = "Possível quebra"
                        tone = "warning"
                    elif status == "QUEBRADO":
                        tone = "danger"
                    results[link_id] = {"status": status, "label": label, "tone": tone, "checked_at": checked_at}
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
    now = timezone.now()
    for link in links:
        link.guardiao = (results or {}).get(link.pk)
        link.guardiao_indisponivel = results is None
        link.ameaca_ativa = bool(link.ameaca_estado == "THREAT" and link.ameaca_verificada_em
                                 and link.ameaca_expira_em and link.ameaca_verificada_em <= now
                                 and link.ameaca_expira_em > now
                                 and now - link.ameaca_verificada_em < timedelta(minutes=30))
        link.seguranca_nao_verificada = not link.ameaca_ativa and not (
            link.ameaca_estado == "NO_MATCH" and link.ameaca_verificada_em
            and link.ameaca_verificada_em <= now and link.ameaca_expira_em and link.ameaca_expira_em > now
        )
    return links


def contar_atencao(user, organizacao):
    # Somente projetos do autor, no ambiente atual. IDs nunca vêm do navegador.
    links = list(ProjectLink.objects.filter(project__owner=user, project__organizacao=organizacao).only("id"))
    results = consultar_links(links)
    if results is None:
        return None
    return sum(item["status"] in {"QUEBRADO", "SEM_RESPOSTA"} for item in results.values())
