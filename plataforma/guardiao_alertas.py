"""Entrega avisos graves sem duplicar usuários ou atravessar organizações."""

import json
import logging
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request

from django.contrib.auth import get_user_model
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import DominioOrganizacao, MembroOrganizacao, Notification, Organizacao

logger = logging.getLogger(__name__)
JORNADAS = {
    "inicio": "a página inicial", "vitrine": "a vitrine de projetos", "entrada": "a entrada",
    "cadastro": "o cadastro", "organizacao": "o acesso da organização",
}


def sincronizar_alertas(endpoint, token, opener):
    """Busca eventos autenticados e confirma somente após o commit das notificações."""
    base = endpoint.removesuffix("/v1/guardiao/links")
    url = base + "/v1/guardiao/alertas/inbox"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with opener.open(Request(url, headers=headers), timeout=10) as response:
            events = json.loads(response.read(65537))
        if not isinstance(events, list) or len(events) > 20:
            raise ValueError("Resposta inválida")
        for event in events:
            event_id, journey, created_at = _validar_evento(event)
            if created_at < timezone.now() - timedelta(hours=24):
                continue  # A API expira eventos antigos sem gerar uma notificação tardia.
            organization = None
            if journey == "organizacao":
                hostname = event.get("tenantHost")
                domain = DominioOrganizacao.objects.select_related("organizacao").filter(
                    hostname__iexact=hostname, status_verificacao="ativo", organizacao__status=Organizacao.STATUS_ATIVA,
                ).first() if isinstance(hostname, str) and hostname else None
                if domain is None:
                    logger.warning("Aviso institucional sem organização ativa correspondente: evento %s.", event_id)
                    _confirmar(opener, url, headers, event_id, "rejeitar")
                    continue
                organization = domain.organizacao
            try:
                _criar_notificacoes(event, event_id, journey, organization, base + "/")
            except DatabaseError as exc:
                _confirmar(opener, url, headers, event_id, "falha")
                raise ValueError("Falha ao gravar avisos") from exc
            _confirmar(opener, url, headers, event_id, "confirmar")
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, TypeError, KeyError) as exc:
        logger.warning("Não foi possível sincronizar os avisos do Guardião.")
        raise ValueError("Sincronização de avisos indisponível") from exc


def _validar_evento(event):
    if not isinstance(event, dict) or isinstance(event.get("id"), bool):
        raise ValueError("Evento inválido")
    event_id, journey = event.get("id"), event.get("journey")
    created_at = parse_datetime(event.get("createdAt") or "")
    started_at = parse_datetime(event.get("startedAt") or "")
    recovered_at = parse_datetime(event.get("recoveredAt") or "") if event.get("recoveredAt") else None
    if (not isinstance(event_id, int) or event_id <= 0 or journey not in JORNADAS
            or not created_at or timezone.is_naive(created_at) or not started_at or timezone.is_naive(started_at)
            or (event.get("recoveredAt") and (not recovered_at or timezone.is_naive(recovered_at)))
            or created_at > timezone.now() + timedelta(minutes=5) or started_at > created_at
            or (recovered_at and recovered_at < started_at)):
        raise ValueError("Evento inválido")
    return event_id, journey, created_at


def _criar_notificacoes(event, event_id, journey, organization, status_url):
    users = get_user_model().objects.filter(is_active=True)
    if organization:
        users = users.filter(afiliacoes_organizacionais__organizacao=organization,
                             afiliacoes_organizacionais__status=MembroOrganizacao.STATUS_ATIVA).distinct()
    kind = "status_incident_tenant" if organization else "status_incident_global"
    message = (f"Uma falha prolongada afetou {JORNADAS[journey]}. "
               + ("O serviço já foi recuperado." if event.get("recoveredAt") else "Acompanhe o status para novidades."))
    with transaction.atomic():
        batch = []
        for user_id in users.values_list("pk", flat=True).iterator(chunk_size=500):
            batch.append(Notification(recipient_id=user_id, kind=kind, message=message, url=status_url,
                                      scope_organization=organization, source_key=f"status-incident:{event_id}"))
            if len(batch) == 500:
                Notification.objects.bulk_create(batch, ignore_conflicts=True)
                batch.clear()
        if batch:
            Notification.objects.bulk_create(batch, ignore_conflicts=True)


def _confirmar(opener, base_url, headers, event_id, action):
    request = Request(f"{base_url}/{event_id}/{action}", data=b"", headers=headers, method="POST")
    with opener.open(request, timeout=10) as response:
        if response.status != 204:
            raise ValueError("Confirmação inválida")
