"""Reavalia links guardados usando o mesmo trabalhador do Guardião."""
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .guardiao_consulta import consultar_ameacas_detalhes
from .models import Notification, ProjectLink
from .rls import system_context


def _project_url(project):
    path = reverse("plataforma:project_detail", kwargs={"pk": project.pk})
    if project.organizacao_id:
        domain = project.organizacao.dominios.filter(status_verificacao="ativo").order_by("-principal", "hostname").first()
        return f"{'http' if settings.DEBUG else 'https'}://{domain.hostname}{path}" if domain else ""
    base = getattr(settings, "PUBLIC_APP_URL", "").rstrip("/")
    if not base:
        base = f"{'http' if settings.DEBUG else 'https'}://{settings.PALACIO_BASE_DOMAIN}"
    return f"{base}{path}"


def verificar_links_salvos():
    now = timezone.now()
    with transaction.atomic(), system_context():
        due = ProjectLink.objects.filter(Q(ameaca_proxima_verificacao__isnull=True) | Q(ameaca_proxima_verificacao__lte=now))
        if connection.features.has_select_for_update_skip_locked:
            due = due.select_for_update(skip_locked=True, of=("self",))
        else:
            due = due.select_for_update()
        links = list(due.select_related("project", "project__owner", "project__organizacao")
                     .order_by("ameaca_proxima_verificacao", "pk")[:6])
        results = consultar_ameacas_detalhes([link.url for link in links])
        if len(results) != len(links):
            results = [{"state": "UNVERIFIED", "checked_at": None, "expires_at": None}] * len(links)
        checked_at = timezone.now()
        for link, detail in zip(links, results):
            result = detail["state"]
            if result != "UNVERIFIED" and (not detail.get("checked_at") or not detail.get("expires_at")
                    or detail["expires_at"] <= checked_at or detail["checked_at"] > checked_at
                    or (result == "THREAT" and checked_at - detail["checked_at"] >= timedelta(minutes=30))):
                result = "UNVERIFIED"
            if result not in {"THREAT", "NO_MATCH"}:
                result = "UNVERIFIED"
            notified = link.ameaca_notificada
            if result == "THREAT" and not notified:
                Notification.objects.create(
                    recipient=link.project.owner, kind="guardiao_ameaca",
                    message=f"Uma verificação anterior apontou um possível risco em uma referência do projeto {link.project.title}. Confira o estado atual dos links."[:280],
                    url=_project_url(link.project),
                )
                notified = True
            elif result == "NO_MATCH":
                notified = False
            if result == "THREAT":
                interval = min(timedelta(minutes=20), max(timedelta(seconds=30), detail["expires_at"] - checked_at))
            elif result == "NO_MATCH":
                interval = min(timedelta(hours=48), max(timedelta(seconds=30), detail["expires_at"] - checked_at))
            else:
                interval = timedelta(minutes=5) if notified else timedelta(hours=1)
            ProjectLink.objects.filter(pk=link.pk, url=link.url).update(
                ameaca_estado=result, ameaca_verificada_em=detail["checked_at"] if result != "UNVERIFIED" else None,
                ameaca_expira_em=detail["expires_at"] if result != "UNVERIFIED" else None,
                ameaca_proxima_verificacao=checked_at + interval, ameaca_notificada=notified,
            )
    return len(links)
