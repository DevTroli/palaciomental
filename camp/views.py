import calendar as pycalendar
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    get_user_model,
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe

from plataforma.models import (
    CollaborationRequest,
    MemberProfile,
    MembroOrganizacao,
    Organizacao,
    Project,
    ProjectMember,
)

from .forms import CampEventoForm, CampPerfilForm, CampProjectForm, CampSenhaForm
from .models import EventoCalendario

# Rótulos e progresso usados apenas na apresentação do dashboard.
# O modelo mantém os status canônicos (ideia, ativo, pausado, concluido).
STATUS_ROTULO = {
    Project.STATUS_IDEA: "Em planejamento",
    Project.STATUS_ACTIVE: "Em desenvolvimento",
    Project.STATUS_PAUSED: "Pausado",
    Project.STATUS_DONE: "Concluído",
}

STATUS_PROGRESSO = {
    Project.STATUS_IDEA: 20,
    Project.STATUS_ACTIVE: 60,
    Project.STATUS_PAUSED: 40,
    Project.STATUS_DONE: 100,
}

STATUS_GRUPO = {
    Project.STATUS_IDEA: "planejamento",
    Project.STATUS_ACTIVE: "andamento",
    Project.STATUS_PAUSED: "andamento",
    Project.STATUS_DONE: "concluidos",
}

# No CAMP, o papel genérico "Membro" aparece como "Aluno".
PAPEL_ROTULO = {
    MembroOrganizacao.PAPEL_MEMBRO: "Aluno",
}

PAPEIS_GESTAO = {
    MembroOrganizacao.PAPEL_PROPRIETARIO,
    MembroOrganizacao.PAPEL_GESTOR,
    MembroOrganizacao.PAPEL_PROFESSOR,
}

INBOX_JANELA_DIAS = 7

MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def _nome_usuario(usuario):
    return usuario.get_full_name() or usuario.username


def _decorar_projetos(projetos):
    for projeto in projetos:
        projeto.rotulo_status = STATUS_ROTULO.get(projeto.status, projeto.get_status_display())
        projeto.progresso = STATUS_PROGRESSO.get(projeto.status, 0)
        projeto.grupo = STATUS_GRUPO.get(projeto.status, "andamento")
        projeto.inicial = (projeto.title or "?")[:1].upper()
    return projetos


def _pode_gerenciar(request):
    """Gestores, professores, proprietários e administradores acessam a gestão."""
    if request.user.is_staff or request.user.is_superuser:
        return True
    membro = getattr(request, "membro_organizacao", None)
    return bool(membro and membro.papel in PAPEIS_GESTAO)


def _inbox_visto(request):
    """Instante da última visita à caixa de entrada, guardado na sessão."""
    valor = request.session.get("camp_inbox_visto")
    if valor:
        try:
            return datetime.fromisoformat(valor)
        except (TypeError, ValueError):
            pass
    return timezone.now() - timedelta(days=INBOX_JANELA_DIAS)


def _itens_inbox(request, visto=None):
    """Reúne atividades novas, colaboradores e pedidos pendentes do aluno."""
    organizacao = getattr(request, "organizacao", None)
    vazio = {"atividades": [], "colaboradores": [], "pedidos": [], "total_novas": 0}
    if organizacao is None:
        return vazio

    visto = visto or _inbox_visto(request)
    hoje = timezone.localdate()

    atividades = list(
        EventoCalendario.objects.filter(
            organizacao=organizacao,
            aluno=request.user,
            origem=EventoCalendario.ORIGEM_ORGANIZACAO,
            tipo=EventoCalendario.TIPO_ATIVIDADE,
            data__gte=hoje,
        ).order_by("data", "horario")[:8]
    )
    for evento in atividades:
        evento.novo = evento.criado_em >= visto

    colaboradores = list(
        ProjectMember.objects.filter(
            project__organizacao=organizacao,
            project__owner=request.user,
        )
        .exclude(user=request.user)
        .select_related("user", "project")
        .order_by("-joined_at")[:8]
    )
    for membro in colaboradores:
        membro.novo = membro.joined_at >= visto
        membro.nome = _nome_usuario(membro.user)

    pedidos = list(
        CollaborationRequest.objects.filter(
            project__organizacao=organizacao,
            project__owner=request.user,
            status=CollaborationRequest.PENDING,
        )
        .select_related("project", "requester")
        .order_by("-created_at")[:8]
    )
    for pedido in pedidos:
        pedido.nome = _nome_usuario(pedido.requester)

    total_novas = (
        sum(1 for evento in atividades if evento.novo)
        + sum(1 for membro in colaboradores if membro.novo)
        + len(pedidos)
    )
    return {
        "atividades": atividades,
        "colaboradores": colaboradores,
        "pedidos": pedidos,
        "total_novas": total_novas,
    }


def _contar_novas_inbox(request):
    """Contagem leve usada no badge do topbar em todas as páginas."""
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or not request.user.is_authenticated:
        return 0

    visto = _inbox_visto(request)
    hoje = timezone.localdate()
    return (
        EventoCalendario.objects.filter(
            organizacao=organizacao,
            aluno=request.user,
            origem=EventoCalendario.ORIGEM_ORGANIZACAO,
            tipo=EventoCalendario.TIPO_ATIVIDADE,
            data__gte=hoje,
            criado_em__gte=visto,
        ).count()
        + ProjectMember.objects.filter(
            project__organizacao=organizacao,
            project__owner=request.user,
            joined_at__gte=visto,
        )
        .exclude(user=request.user)
        .count()
        + CollaborationRequest.objects.filter(
            project__organizacao=organizacao,
            project__owner=request.user,
            status=CollaborationRequest.PENDING,
        ).count()
    )


def _contexto_base(request):
    """Dados comuns a todas as páginas do CAMP (topbar e menu lateral)."""
    organizacao = getattr(request, "organizacao", None)
    membro = getattr(request, "membro_organizacao", None)
    total_membros = 0
    if organizacao:
        total_membros = MembroOrganizacao.objects.filter(
            organizacao=organizacao,
            status=MembroOrganizacao.STATUS_ATIVA,
        ).count()
    return {
        "organizacao": organizacao,
        "membro": membro,
        "total_membros": total_membros,
        "nome_usuario": _nome_usuario(request.user) if request.user.is_authenticated else "",
        "papel_usuario": (
            PAPEL_ROTULO.get(membro.papel, membro.get_papel_display()) if membro else "Aluno"
        ),
        "pode_gerenciar": _pode_gerenciar(request),
        "inbox_novas": _contar_novas_inbox(request),
    }


def _projeto_do_usuario(request, pk):
    """Garante que o projeto é do usuário e do tenant atual."""
    return get_object_or_404(
        Project,
        pk=pk,
        owner=request.user,
        organizacao=getattr(request, "organizacao", None),
    )


@require_safe
def demo_login(request):
    """Acesso rápido de desenvolvimento ao CAMP, sem passar pelo cadastro.

    Só existe com DEBUG=True. Entra com o primeiro aluno ativo da organização
    resolvida pelo subdomínio e redireciona para o dashboard.
    """
    if not settings.DEBUG:
        raise Http404

    organizacao = getattr(request, "organizacao", None) or _organizacao_demo()
    if organizacao is None:
        messages.info(request, "Acesso de demonstração disponível apenas no ambiente institucional.")
        return redirect("plataforma:login")

    membro = (
        MembroOrganizacao.objects.filter(
            organizacao=organizacao,
            status=MembroOrganizacao.STATUS_ATIVA,
        )
        .select_related("usuario")
        .annotate(
            total_projetos=Count("usuario__owned_projects", distinct=True),
            total_participacoes=Count("usuario__project_memberships", distinct=True),
        )
        .order_by("-total_projetos", "-total_participacoes", "usuario__username")
        .first()
    )
    if membro is None:
        messages.error(request, "Nenhum aluno ativo encontrado para o acesso de demonstração.")
        return redirect("plataforma:login")
    auth_login(request, membro.usuario, backend="django.contrib.auth.backends.ModelBackend")
    destino = request.GET.get("next", "")
    if not (destino == "/camp" or destino.startswith("/camp/")):
        destino = ""
    return redirect(destino or "camp:dashboard")


def _organizacao_demo():
    """Organização ativa usada pelo acesso de demonstração quando o tenant
    ainda não foi resolvido (por exemplo, em desenvolvimento na raiz)."""
    return Organizacao.objects.filter(status=Organizacao.STATUS_ATIVA).order_by("pk").first()


@require_safe
def camp_register(request):
    """Página de cadastro institucional do CAMP.

    Diferente do cadastro institucional do Palácio Mental, a entrada do CAMP
    é a própria experiência do ambiente: os alunos entram pelo modo demonstração
    sem precisar criar conta.
    """
    if request.user.is_authenticated:
        return redirect("camp:dashboard")

    context = _contexto_base(request)
    context["nav_ativo"] = "inicio"
    return render(request, "camp/register.html", context)


@login_required
def dashboard(request):
    """Dashboard principal do CAMP — ambiente institucional do tenant.

    Só acessível via subdomínio institucional (middleware já garante que
    request.organizacao e request.membro_organizacao estão disponíveis).
    """
    context = _contexto_base(request)
    context["nav_ativo"] = "inicio"

    organizacao = context["organizacao"]
    if organizacao:
        projetos = (
            Project.objects.filter(organizacao=organizacao)
            .select_related("owner")
            .annotate(
                total_membros=Count("memberships", distinct=True),
                total_estrelas=Count("votes", distinct=True),
            )
        )
        pessoais = (
            projetos.filter(
                Q(owner=request.user) | Q(memberships__user=request.user)
            )
            .distinct()
            .order_by("-updated_at")[:1]
        )
        da_organizacao = (
            projetos.filter(visibility=Project.VISIBILITY_PUBLIC)
            .exclude(Q(owner=request.user) | Q(memberships__user=request.user))
            .distinct()
            .order_by("-updated_at")[:1]
        )
        ranking = (
            projetos.filter(visibility=Project.VISIBILITY_PUBLIC)
            .order_by("-total_estrelas", "-total_membros", "-updated_at")[:3]
        )
        context.update(
            {
                "projetos_pessoais": _decorar_projetos(list(pessoais)),
                "projetos_camp": _decorar_projetos(list(da_organizacao)),
                "ranking_projetos": _decorar_projetos(list(ranking)),
            }
        )
    else:
        context.update(
            {
                "projetos_pessoais": [],
                "projetos_camp": [],
                "ranking_projetos": [],
            }
        )

    return render(request, "camp/dashboard.html", context)


@login_required
def history(request):
    """Página institucional com a história e a identidade do CAMP."""
    context = _contexto_base(request)
    context["nav_ativo"] = "historia"
    return render(request, "camp/history.html", context)


@login_required
def profile(request):
    """Perfil do aluno: dados, calendário, projetos, colaborações e ajustes."""
    context = _contexto_base(request)
    organizacao = context["organizacao"]
    hoje = date.today()

    aba_ativa = request.GET.get("aba") or "projetos"
    if aba_ativa not in {"projetos", "colaboracoes", "configuracoes"}:
        aba_ativa = "projetos"

    try:
        ano = int(request.GET.get("ano", hoje.year))
        mes = int(request.GET.get("mes", hoje.month))
        primeiro_dia = date(ano, mes, 1)
    except (TypeError, ValueError):
        ano, mes = hoje.year, hoje.month
        primeiro_dia = date(ano, mes, 1)

    form_perfil = CampPerfilForm(instance=request.user)
    form_senha = CampSenhaForm(request.user)
    perfil_usuario, _ = MemberProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        aba_ativa = "configuracoes"
        if request.POST.get("form") == "senha":
            form_senha = CampSenhaForm(request.user, request.POST)
            if form_senha.is_valid():
                form_senha.save()
                update_session_auth_hash(request, form_senha.user)
                messages.success(request, "Senha alterada com sucesso.")
                return redirect(f"{reverse('camp:profile')}?aba=configuracoes")
        else:
            form_perfil = CampPerfilForm(
                request.POST,
                request.FILES,
                instance=request.user,
            )
            if form_perfil.is_valid():
                form_perfil.save()
                if form_perfil.cleaned_data.get("remover_avatar"):
                    if perfil_usuario.avatar:
                        perfil_usuario.avatar.delete(save=False)
                    perfil_usuario.avatar = ""
                elif form_perfil.cleaned_data.get("avatar"):
                    if perfil_usuario.avatar:
                        perfil_usuario.avatar.delete(save=False)
                    perfil_usuario.avatar = form_perfil.cleaned_data["avatar"]
                perfil_usuario.save()
                messages.success(request, "Dados do perfil atualizados.")
                return redirect(f"{reverse('camp:profile')}?aba=configuracoes")

    meus_projetos = []
    projetos_institucionais = []
    inscricoes = []

    if organizacao:
        projetos = (
            Project.objects.filter(organizacao=organizacao)
            .select_related("owner")
            .annotate(
                total_membros=Count("memberships", distinct=True),
                total_estrelas=Count("votes", distinct=True),
            )
        )
        meus_projetos = _decorar_projetos(
            list(
                projetos.filter(owner=request.user).order_by("-updated_at")
            )
        )
        projetos_institucionais = _decorar_projetos(
            list(
                projetos.filter(visibility=Project.VISIBILITY_PUBLIC)
                .exclude(
                    Q(owner=request.user) | Q(memberships__user=request.user)
                )
                .distinct()
                .order_by("-updated_at")[:6]
            )
        )
        inscricoes = list(
            ProjectMember.objects.filter(
                user=request.user,
                project__organizacao=organizacao,
            )
            .exclude(project__owner=request.user)
            .select_related("project", "project__owner")
            .order_by("-joined_at")
        )
        for inscricao in inscricoes:
            _decorar_projetos([inscricao.project])

    eventos = []
    if organizacao:
        eventos = list(
            EventoCalendario.objects.filter(
                organizacao=organizacao,
                aluno=request.user,
            ).select_related("projeto")
        )

    eventos_por_dia = {}
    for evento in eventos:
        eventos_por_dia.setdefault(evento.data, []).append(evento)

    semanas = []
    for semana in pycalendar.Calendar(firstweekday=0).monthdatescalendar(ano, mes):
        dias = []
        for dia in semana:
            dias.append(
                {
                    "data": dia,
                    "numero": dia.day,
                    "fora_do_mes": dia.month != mes,
                    "hoje": dia == hoje,
                    "eventos": sorted(
                        eventos_por_dia.get(dia, []),
                        key=_chave_ordenacao,
                    ),
                }
            )
        semanas.append(dias)

    proximas_atividades = sorted(
        [evento for evento in eventos if evento.data >= hoje],
        key=_chave_ordenacao,
    )[:3]

    anterior = (primeiro_dia - timedelta(days=1)).replace(day=1)
    proximo = (primeiro_dia + timedelta(days=32)).replace(day=1)

    context.update(
        {
            "nav_ativo": "perfil",
            "aba_ativa": aba_ativa,
            "form_perfil": form_perfil,
            "form_senha": form_senha,
            "perfil_usuario": perfil_usuario,
            "meus_projetos": meus_projetos,
            "projetos_institucionais": projetos_institucionais,
            "inscricoes": inscricoes,
            "total_projetos": len(meus_projetos),
            "total_institucionais": len(projetos_institucionais),
            "total_inscricoes": len(inscricoes),
            "total_concluidos": sum(
                1 for projeto in meus_projetos if projeto.status == Project.STATUS_DONE
            ),
            "ano": ano,
            "mes": mes,
            "mes_nome": MESES[mes - 1],
            "hoje": hoje,
            "semanas": semanas,
            "proximas_atividades": proximas_atividades,
            "ano_anterior": anterior.year,
            "mes_anterior": anterior.month,
            "ano_proximo": proximo.year,
            "mes_proximo": proximo.month,
            "inicial_usuario": (context["nome_usuario"] or "?")[:1].upper(),
        }
    )
    return render(request, "camp/profile.html", context)


@login_required
def project_create(request):
    """Cria um projeto próprio dentro do CAMP."""
    form = CampProjectForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        projeto = form.save(commit=False)
        projeto.owner = request.user
        projeto.organizacao = getattr(request, "organizacao", None)
        projeto.save()
        messages.success(request, "Projeto criado com sucesso.")
        return redirect("camp:profile")

    context = _contexto_base(request)
    context.update(
        {
            "nav_ativo": "perfil",
            "form": form,
            "modo": "criar",
            "titulo_pagina": "Novo projeto",
        }
    )
    return render(request, "camp/project_form.html", context)


@login_required
def project_edit(request, pk):
    """Edita um projeto do próprio usuário."""
    projeto = _projeto_do_usuario(request, pk)
    form = CampProjectForm(request.POST or None, instance=projeto, owner=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Projeto atualizado com sucesso.")
        return redirect("camp:profile")

    context = _contexto_base(request)
    context.update(
        {
            "nav_ativo": "perfil",
            "form": form,
            "modo": "editar",
            "projeto": projeto,
            "titulo_pagina": f"Editar {projeto.title}",
        }
    )
    return render(request, "camp/project_form.html", context)


@login_required
@require_POST
def project_delete(request, pk):
    """Exclui um projeto do próprio usuário."""
    projeto = _projeto_do_usuario(request, pk)
    titulo = projeto.title
    projeto.delete()
    messages.success(request, f"O projeto “{titulo}” foi excluído.")
    return redirect("camp:profile")


def _chave_ordenacao(evento):
    return (evento.data, evento.horario or time.min, evento.titulo)


@login_required
def calendar_view(request):
    """Calendário do aluno com atividades e trabalhos para entregar."""
    context = _contexto_base(request)
    organizacao = context["organizacao"]
    hoje = date.today()

    try:
        ano = int(request.GET.get("ano", hoje.year))
        mes = int(request.GET.get("mes", hoje.month))
        primeiro_dia = date(ano, mes, 1)
    except (TypeError, ValueError):
        ano, mes = hoje.year, hoje.month
        primeiro_dia = date(ano, mes, 1)

    eventos = []
    if organizacao:
        eventos = list(
            EventoCalendario.objects.filter(
                organizacao=organizacao,
                aluno=request.user,
            ).select_related("projeto")
        )

    eventos_por_dia = {}
    for evento in eventos:
        eventos_por_dia.setdefault(evento.data, []).append(evento)

    semanas = []
    for semana in pycalendar.Calendar(firstweekday=0).monthdatescalendar(ano, mes):
        dias = []
        for dia in semana:
            dias.append(
                {
                    "data": dia,
                    "numero": dia.day,
                    "fora_do_mes": dia.month != mes,
                    "hoje": dia == hoje,
                    "eventos": sorted(
                        eventos_por_dia.get(dia, []),
                        key=_chave_ordenacao,
                    ),
                }
            )
        semanas.append(dias)

    eventos_mes = sorted(
        [evento for evento in eventos if evento.data.year == ano and evento.data.month == mes],
        key=_chave_ordenacao,
    )

    dias_com_eventos = []
    for evento in eventos_mes:
        if not dias_com_eventos or dias_com_eventos[-1]["data"] != evento.data:
            dias_com_eventos.append({"data": evento.data, "eventos": []})
        dias_com_eventos[-1]["eventos"].append(evento)

    trabalhos_pendentes = sorted(
        [
            evento
            for evento in eventos
            if evento.tipo == EventoCalendario.TIPO_TRABALHO
            and evento.status == EventoCalendario.STATUS_PENDENTE
        ],
        key=_chave_ordenacao,
    )[:5]

    proximas_atividades = sorted(
        [
            evento
            for evento in eventos
            if evento.tipo == EventoCalendario.TIPO_ATIVIDADE and evento.data >= hoje
        ],
        key=_chave_ordenacao,
    )[:5]

    total_pendentes = sum(
        1
        for evento in eventos
        if evento.tipo == EventoCalendario.TIPO_TRABALHO
        and evento.status == EventoCalendario.STATUS_PENDENTE
    )
    total_entregues = sum(
        1
        for evento in eventos
        if evento.tipo == EventoCalendario.TIPO_TRABALHO
        and evento.status == EventoCalendario.STATUS_ENTREGUE
    )

    anterior = (primeiro_dia - timedelta(days=1)).replace(day=1)
    proximo = (primeiro_dia + timedelta(days=32)).replace(day=1)

    meus_eventos_mes = [
        evento for evento in eventos_mes if evento.origem == EventoCalendario.ORIGEM_ALUNO
    ]

    context.update(
        {
            "nav_ativo": "calendario",
            "ano": ano,
            "mes": mes,
            "mes_nome": MESES[mes - 1],
            "hoje": hoje,
            "semanas": semanas,
            "eventos_mes": eventos_mes,
            "meus_eventos_mes": meus_eventos_mes,
            "dias_com_eventos": dias_com_eventos,
            "trabalhos_pendentes": trabalhos_pendentes,
            "proximas_atividades": proximas_atividades,
            "total_pendentes": total_pendentes,
            "total_entregues": total_entregues,
            "total_atividades_mes": sum(
                1 for evento in eventos_mes if evento.tipo == EventoCalendario.TIPO_ATIVIDADE
            ),
            "ano_anterior": anterior.year,
            "mes_anterior": anterior.month,
            "ano_proximo": proximo.year,
            "mes_proximo": proximo.month,
        }
    )
    return render(request, "camp/calendar.html", context)


@login_required
@require_POST
def calendar_toggle(request, pk):
    """Marca ou desmarca um trabalho como entregue."""
    evento = get_object_or_404(
        EventoCalendario,
        pk=pk,
        organizacao=getattr(request, "organizacao", None),
        aluno=request.user,
        tipo=EventoCalendario.TIPO_TRABALHO,
    )
    if evento.status == EventoCalendario.STATUS_ENTREGUE:
        evento.status = EventoCalendario.STATUS_PENDENTE
        messages.info(request, f"“{evento.titulo}” voltou para pendente.")
    else:
        evento.status = EventoCalendario.STATUS_ENTREGUE
        messages.success(request, f"“{evento.titulo}” marcado como entregue.")
    evento.save(update_fields=["status"])

    destino = reverse("camp:calendar")
    return redirect(f"{destino}?ano={evento.data.year}&mes={evento.data.month}")


def _evento_do_aluno(request, pk):
    """Garante que o evento foi criado pelo aluno e pertence ao tenant atual."""
    return get_object_or_404(
        EventoCalendario,
        pk=pk,
        organizacao=getattr(request, "organizacao", None),
        aluno=request.user,
        origem=EventoCalendario.ORIGEM_ALUNO,
    )


def _redirecionar_calendario(evento):
    return redirect(
        f"{reverse('camp:calendar')}?ano={evento.data.year}&mes={evento.data.month}"
    )


@login_required
def event_create(request):
    """Cria um evento pessoal no calendário do aluno."""
    organizacao = getattr(request, "organizacao", None)
    initial = {}
    data_inicial = (request.GET.get("data") or "").strip()
    if data_inicial:
        try:
            initial["data"] = date.fromisoformat(data_inicial)
        except ValueError:
            pass
    tipo_inicial = (request.GET.get("tipo") or "").strip()
    if tipo_inicial in dict(EventoCalendario.TIPO_CHOICES):
        initial["tipo"] = tipo_inicial

    form = CampEventoForm(
        request.POST or None,
        aluno=request.user,
        organizacao=organizacao,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        evento = form.save(commit=False)
        evento.organizacao = organizacao
        evento.aluno = request.user
        evento.origem = EventoCalendario.ORIGEM_ALUNO
        evento.save()
        messages.success(request, f"O evento “{evento.titulo}” foi adicionado ao seu calendário.")
        return _redirecionar_calendario(evento)

    context = _contexto_base(request)
    context.update(
        {
            "nav_ativo": "calendario",
            "form": form,
            "modo": "criar",
            "titulo_pagina": "Novo evento",
            "hoje": date.today(),
        }
    )
    return render(request, "camp/event_form.html", context)


@login_required
def event_edit(request, pk):
    """Edita um evento criado pelo próprio aluno."""
    evento = _evento_do_aluno(request, pk)
    form = CampEventoForm(
        request.POST or None,
        instance=evento,
        aluno=request.user,
        organizacao=evento.organizacao,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"O evento “{evento.titulo}” foi atualizado.")
        return _redirecionar_calendario(evento)

    context = _contexto_base(request)
    context.update(
        {
            "nav_ativo": "calendario",
            "form": form,
            "modo": "editar",
            "evento": evento,
            "titulo_pagina": f"Editar {evento.titulo}",
            "hoje": date.today(),
        }
    )
    return render(request, "camp/event_form.html", context)


@login_required
@require_POST
def event_delete(request, pk):
    """Exclui um evento criado pelo próprio aluno."""
    evento = _evento_do_aluno(request, pk)
    titulo = evento.titulo
    ano, mes = evento.data.year, evento.data.month
    evento.delete()
    messages.success(request, f"O evento “{titulo}” foi excluído do seu calendário.")
    return redirect(f"{reverse('camp:calendar')}?ano={ano}&mes={mes}")


@login_required
def explore(request):
    """Descobre projetos abertos a colaboração e alunos do CAMP."""
    context = _contexto_base(request)
    organizacao = context["organizacao"]

    vista = request.GET.get("vista", "projetos")
    if vista not in ("projetos", "alunos"):
        vista = "projetos"
    busca = (request.GET.get("q") or "").strip()
    categoria = (request.GET.get("categoria") or "").strip()
    aluno_filtro = (request.GET.get("aluno") or "").strip()

    projetos_abertos = []
    colaboradores = []
    categorias = []
    aluno_filtro_nome = ""
    total_projetos_abertos = 0
    total_colaboradores = 0
    total_participacoes = 0

    if organizacao:
        base_projetos = (
            Project.objects.filter(
                organizacao=organizacao,
                visibility=Project.VISIBILITY_PUBLIC,
                seeking_collaborators=True,
            )
            .exclude(Q(owner=request.user) | Q(memberships__user=request.user))
            .select_related("owner")
            .annotate(total_membros=Count("memberships", distinct=True))
        )
        total_projetos_abertos = base_projetos.count()

        if busca:
            base_projetos = base_projetos.filter(
                Q(title__icontains=busca)
                | Q(direction__icontains=busca)
                | Q(category__icontains=busca)
                | Q(tags__icontains=busca)
                | Q(collaboration_description__icontains=busca)
                | Q(owner__username__icontains=busca)
                | Q(owner__first_name__icontains=busca)
                | Q(owner__last_name__icontains=busca)
            )
        if categoria:
            base_projetos = base_projetos.filter(category__iexact=categoria)
        if aluno_filtro:
            base_projetos = base_projetos.filter(owner__username=aluno_filtro)
        projetos_abertos = _decorar_projetos(list(base_projetos.order_by("-updated_at")))

        membros_ativos = MembroOrganizacao.objects.filter(
            organizacao=organizacao,
            status=MembroOrganizacao.STATUS_ATIVA,
        ).exclude(usuario=request.user)
        total_colaboradores = membros_ativos.count()
        total_participacoes = ProjectMember.objects.filter(
            user=request.user,
            project__organizacao=organizacao,
        ).count()

        projetos_publicos = Project.objects.filter(
            organizacao=organizacao,
            visibility=Project.VISIBILITY_PUBLIC,
        ).only("id", "owner_id", "title", "category")
        membros_qs = (
            membros_ativos.select_related("usuario")
            .prefetch_related(
                Prefetch(
                    "usuario__owned_projects",
                    queryset=projetos_publicos,
                    to_attr="projetos_publicos",
                )
            )
        )
        if busca:
            membros_qs = membros_qs.filter(
                Q(usuario__username__icontains=busca)
                | Q(usuario__first_name__icontains=busca)
                | Q(usuario__last_name__icontains=busca)
                | Q(usuario__owned_projects__title__icontains=busca)
                | Q(usuario__owned_projects__category__icontains=busca)
            ).distinct()
        if categoria:
            membros_qs = membros_qs.filter(
                usuario__owned_projects__category__iexact=categoria,
                usuario__owned_projects__organizacao=organizacao,
                usuario__owned_projects__visibility=Project.VISIBILITY_PUBLIC,
            ).distinct()

        for membro in membros_qs.order_by("usuario__first_name", "usuario__username"):
            membro.nome = _nome_usuario(membro.usuario)
            membro.inicial = membro.nome[:1].upper()
            membro.papel_rotulo = PAPEL_ROTULO.get(
                membro.papel, membro.get_papel_display()
            )
            projetos = getattr(membro.usuario, "projetos_publicos", [])
            membro.total_projetos = len(projetos)
            membro.categorias = sorted(
                {projeto.category for projeto in projetos if projeto.category}
            )[:4]
            colaboradores.append(membro)

        categorias = list(
            Project.objects.filter(
                organizacao=organizacao,
                visibility=Project.VISIBILITY_PUBLIC,
            )
            .exclude(category="")
            .values_list("category", flat=True)
            .distinct()
            .order_by("category")
        )

        if aluno_filtro:
            usuario = get_user_model().objects.filter(username=aluno_filtro).first()
            if usuario:
                aluno_filtro_nome = _nome_usuario(usuario)

    context.update(
        {
            "nav_ativo": "alunos" if vista == "alunos" else "explorar",
            "vista": vista,
            "busca": busca,
            "categoria": categoria,
            "aluno_filtro": aluno_filtro,
            "aluno_filtro_nome": aluno_filtro_nome,
            "categorias": categorias,
            "projetos_abertos": projetos_abertos,
            "colaboradores": colaboradores,
            "total_projetos_abertos": total_projetos_abertos,
            "total_colaboradores": total_colaboradores,
            "total_participacoes": total_participacoes,
        }
    )
    return render(request, "camp/explore.html", context)


def _destino_colaboracao(request):
    destino = (request.POST.get("next") or "").strip()
    if destino == "/camp" or destino.startswith("/camp/"):
        return destino
    return reverse("camp:explore")


@login_required
@require_POST
def join_project(request, pk):
    """Entra na colaboração de um projeto aberto do tenant."""
    projeto = get_object_or_404(
        Project,
        pk=pk,
        organizacao=getattr(request, "organizacao", None),
        visibility=Project.VISIBILITY_PUBLIC,
        seeking_collaborators=True,
    )
    destino = _destino_colaboracao(request)

    if projeto.owner_id == request.user.id:
        messages.info(request, "Este projeto já é seu.")
        return redirect(destino)

    _, criado = ProjectMember.objects.get_or_create(
        project=projeto,
        user=request.user,
        defaults={"role": "Colaborador"},
    )
    if criado:
        messages.success(
            request,
            f"Você entrou na colaboração do projeto “{projeto.title}”.",
        )
    else:
        messages.info(request, f"Você já participa do projeto “{projeto.title}”.")
    return redirect(destino)


@login_required
@require_POST
def leave_project(request, pk):
    """Sai da colaboração de um projeto do qual o aluno participa."""
    projeto = get_object_or_404(
        Project,
        pk=pk,
        organizacao=getattr(request, "organizacao", None),
    )
    if projeto.owner_id == request.user.id:
        messages.error(request, "Você não pode sair do seu próprio projeto.")
        return redirect("camp:profile")

    removidos, _ = ProjectMember.objects.filter(
        project=projeto,
        user=request.user,
    ).delete()
    if removidos:
        messages.success(request, f"Você saiu da colaboração do projeto “{projeto.title}”.")
    else:
        messages.info(request, "Você não participa deste projeto.")
    return redirect("camp:profile")


@login_required
def inbox(request):
    """Caixa de entrada do aluno: atividades novas e novas colaborações."""
    context = _contexto_base(request)
    dados = _itens_inbox(request)
    context.update(
        {
            "nav_ativo": "inbox",
            "atividades": dados["atividades"],
            "colaboradores": dados["colaboradores"],
            "pedidos": dados["pedidos"],
            "total_novas": dados["total_novas"],
            "inbox_novas": 0,
            "hoje": timezone.localdate(),
        }
    )
    request.session["camp_inbox_visto"] = timezone.now().isoformat()
    return render(request, "camp/inbox.html", context)


@login_required
@require_POST
def inbox_decide(request, pk):
    """Aceita ou recusa um pedido de colaboração em um projeto do aluno."""
    pedido = get_object_or_404(
        CollaborationRequest,
        pk=pk,
        project__organizacao=getattr(request, "organizacao", None),
        project__owner=request.user,
        status=CollaborationRequest.PENDING,
    )
    decisao = request.POST.get("decision")
    if decisao not in (CollaborationRequest.ACCEPTED, CollaborationRequest.REJECTED):
        messages.error(request, "Escolha aceitar ou recusar o pedido.")
        return redirect("camp:inbox")

    projeto = pedido.project
    solicitante = pedido.requester
    if decisao == CollaborationRequest.ACCEPTED:
        ProjectMember.objects.get_or_create(
            project=projeto,
            user=solicitante,
            defaults={"role": "Colaborador"},
        )
        messages.success(
            request,
            f"{_nome_usuario(solicitante)} agora colabora em “{projeto.title}”.",
        )
    else:
        messages.info(
            request,
            f"O pedido de {_nome_usuario(solicitante)} para “{projeto.title}” foi recusado.",
        )
    pedido.delete()
    return redirect("camp:inbox")


@login_required
def manage(request):
    """Painel de gestão do CAMP, disponível para gestores e professores."""
    if not _pode_gerenciar(request):
        raise Http404

    context = _contexto_base(request)
    organizacao = context["organizacao"]
    if organizacao is None:
        raise Http404

    membros = list(
        MembroOrganizacao.objects.filter(
            organizacao=organizacao,
            status=MembroOrganizacao.STATUS_ATIVA,
        )
        .select_related("usuario")
        .order_by("usuario__first_name", "usuario__username")
    )
    for membro in membros:
        membro.nome = _nome_usuario(membro.usuario)
        membro.inicial = membro.nome[:1].upper()
        membro.papel_rotulo = PAPEL_ROTULO.get(membro.papel, membro.get_papel_display())

    projetos = _decorar_projetos(
        list(
            Project.objects.filter(organizacao=organizacao)
            .select_related("owner")
            .annotate(total_membros=Count("memberships", distinct=True))
            .order_by("-updated_at")
        )
    )

    pedidos = list(
        CollaborationRequest.objects.filter(
            project__organizacao=organizacao,
            status=CollaborationRequest.PENDING,
        )
        .select_related("project", "requester")
        .order_by("-created_at")
    )
    for pedido in pedidos:
        pedido.nome = _nome_usuario(pedido.requester)

    context.update(
        {
            "nav_ativo": "gestao",
            "membros": membros,
            "projetos": projetos,
            "pedidos": pedidos,
            "total_alunos": sum(
                1 for membro in membros if membro.papel == MembroOrganizacao.PAPEL_MEMBRO
            ),
            "total_projetos": len(projetos),
            "total_abertos": sum(1 for projeto in projetos if projeto.seeking_collaborators),
            "total_pedidos": len(pedidos),
        }
    )
    return render(request, "camp/manage.html", context)


@login_required
@require_POST
def logout_view(request):
    """Encerra a sessão e volta para a entrada do ambiente institucional."""
    auth_logout(request)
    return redirect(settings.LOGIN_URL)
