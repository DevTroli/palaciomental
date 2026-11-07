"""Agenda institucional: tenant, destinatário e origem são contratos do servidor."""

import calendar
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from .agenda import visible_events
from .agenda_forms import EventoInstitucionalForm, PublicacaoAtividadeForm
from .decorators import tenant_required
from .models import EventoCalendario
from django.http import HttpResponseForbidden


def _scope(request):
    return EventoCalendario.objects.filter(organizacao=request.organizacao, aluno=request.user)


def _month(request):
    today = timezone.localdate()
    try:
        year, month = int(request.GET.get("ano", today.year)), int(request.GET.get("mes", today.month))
        if not 2 <= year <= 9998:
            raise ValueError
        return date(year, month, 1)
    except (TypeError, ValueError):
        return today.replace(day=1)


def _back(event):
    return redirect(f"{reverse('plataforma:calendar')}?ano={event.data.year}&mes={event.data.month}")


@login_required
@tenant_required
def calendar_view(request):
    month = _month(request)
    today = timezone.localdate()
    previous = (month - timedelta(days=1)).replace(day=1)
    following = (month + timedelta(days=32)).replace(day=1)
    dates = calendar.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month)
    queryset = _scope(request)
    events = visible_events(queryset.filter(data__range=(dates[0][0], dates[-1][-1])).select_related("projeto"), request)
    by_day = {}
    for event in events:
        by_day.setdefault(event.data, []).append(event)
    monthly = [event for event in events if event.data.month == month.month and event.data.year == month.year]
    totals = queryset.aggregate(
        pending=Count("pk", filter=Q(tipo="trabalho", status="pendente")),
        delivered=Count("pk", filter=Q(tipo="trabalho", status="entregue")),
    )
    return render(request, "institutional/experience/calendar.html", {
        "nav_ativo": "calendario", "ano": month.year, "mes": month.month,
        "mes_nome": date_format(month, "F"), "hoje": today,
        "ano_anterior": previous.year, "mes_anterior": previous.month,
        "ano_proximo": following.year, "mes_proximo": following.month,
        "semanas": [[{"data": day, "numero": day.day, "fora_do_mes": day.month != month.month,
                      "hoje": day == today, "eventos": by_day.get(day, [])} for day in week] for week in dates],
        "dias_com_eventos": [{"data": day, "eventos": by_day[day]} for day in sorted(by_day) if day.month == month.month and day.year == month.year],
        "meus_eventos_mes": [event for event in monthly if event.origem == EventoCalendario.ORIGEM_ALUNO],
        "trabalhos_pendentes": visible_events(queryset.filter(tipo="trabalho", status="pendente").select_related("projeto")[:5], request),
        "proximas_atividades": visible_events(queryset.filter(tipo="atividade", data__gte=today).select_related("projeto")[:5], request),
        "total_pendentes": totals["pending"], "total_entregues": totals["delivered"],
        "total_atividades_mes": sum(event.tipo == "atividade" for event in monthly),
    })


@login_required
@tenant_required
def event_create(request):
    return _edit(request)


@login_required
@tenant_required
def event_edit(request, pk):
    event = get_object_or_404(_scope(request), pk=pk, origem=EventoCalendario.ORIGEM_ALUNO)
    return _edit(request, event)


def _edit(request, event=None):
    initial = {}
    try:
        initial["data"] = date.fromisoformat(request.GET.get("data", ""))
    except (TypeError, ValueError):
        pass
    form = EventoInstitucionalForm(request.POST or None, instance=event, initial=initial,
                                   organizacao=request.organizacao, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        messages.success(request, "Evento salvo no seu calendário institucional.")
        return _back(event)
    return render(request, "institutional/experience/event_form.html", {
        "form": form, "evento": event, "modo": "editar" if event else "criar",
        "titulo_pagina": "Editar evento" if event else "Novo evento", "nav_ativo": "calendario",
    })


@login_required
@tenant_required
@require_POST
def event_delete(request, pk):
    event = get_object_or_404(_scope(request), pk=pk, origem=EventoCalendario.ORIGEM_ALUNO)
    response = _back(event)
    event.delete()
    messages.success(request, "Evento excluído.")
    return response


@login_required
@tenant_required
@require_POST
def calendar_toggle(request, pk):
    event = get_object_or_404(_scope(request), pk=pk, tipo=EventoCalendario.TIPO_TRABALHO)
    event.status = (EventoCalendario.STATUS_PENDENTE if event.status == EventoCalendario.STATUS_ENTREGUE
                    else EventoCalendario.STATUS_ENTREGUE)
    event.save(update_fields=["status"])
    return _back(event)


@login_required
@tenant_required
def event_publish(request):
    if request.membro_organizacao.papel not in {"gestor", "proprietario"}:
        return HttpResponseForbidden("Somente a gestão pode publicar atividades institucionais.")
    form = PublicacaoAtividadeForm(request.POST or None, organizacao=request.organizacao, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Atividade publicada no calendário do participante.")
        return redirect("plataforma:institutional_management")
    return render(request, "institutional/experience/event_form.html", {
        "form": form, "modo": "publicar", "titulo_pagina": "Publicar atividade institucional",
        "nav_ativo": "gestao",
    })
