import calendar as pycalendar
import logging
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, transaction
from django.db.models import Count, Prefetch, Q
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe

from .models import (
    CollaborationRequest,
    MemberProfile,
    MembroOrganizacao,
    MembroGrupo,
    Organizacao,
    Project,
    ProjectMember,
    Notification,
)

from .experience_forms import PerfilInstitucionalForm, SenhaInstitucionalForm
from .models import EventoCalendario
from .agenda import visible_events
from .decorators import tenant_required

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



def _inbox_visto(request):
    """Instante da última visita à caixa de entrada, guardado na sessão."""
    valor = request.session.get(f"tenant:{request.organizacao.pk}:inbox_visto")
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
        ).select_related("projeto").order_by("data", "horario")[:8]
    )
    atividades = visible_events(atividades, request)
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
        + _notificacoes_tenant(request, nao_lidas=True).count()
    )


def _notificacoes_tenant(request, *, nao_lidas=False):
    """Restringe notificações ao domínio atual do tenant."""
    domains = request.organizacao.dominios.filter(status_verificacao="ativo").values_list("hostname", flat=True)
    urls = Q(pk__in=[])
    for domain in domains:
        urls |= Q(url__startswith=f"https://{domain}/") | Q(url__startswith=f"http://{domain}/")
    queryset = Notification.objects.filter(recipient=request.user).filter(urls)
    return queryset.filter(read_at__isnull=True) if nao_lidas else queryset



def _contexto_base(request):
    """Dados comuns a todas as páginas do ambiente (topbar e menu lateral)."""
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
        "pode_gerenciar": bool(membro and membro.papel in {"gestor", "proprietario"}),
        "inbox_novas": 0,
    }



@tenant_required
@login_required
@require_safe
def classes_and_teams(request):
    """Apresenta o espaço institucional reservado a turmas e equipes."""
    context = _contexto_base(request)
    context["nav_ativo"] = "turmas_e_equipes"
    return render(request, "institutional/experience/classes_and_teams.html", context)


@tenant_required
@login_required
@require_safe
def guidance(request):
    """Exibe informações institucionais e o espaço reservado a avisos."""
    return render(request, "institutional/experience/guidance.html", _contexto_base(request))


def _processar_atualizacao_perfil(request, perfil_usuario):
    form_perfil = PerfilInstitucionalForm(instance=request.user)
    form_senha = SenhaInstitucionalForm(request.user)
    if request.method != "POST":
        return form_perfil, form_senha, None
    if request.POST.get("form") == "senha":
        form_senha = SenhaInstitucionalForm(request.user, request.POST)
        if form_senha.is_valid():
            form_senha.save()
            update_session_auth_hash(request, form_senha.user)
            messages.success(request, "Senha alterada com sucesso.")
            return form_perfil, form_senha, redirect(
                f"{reverse('plataforma:institutional_profile')}?aba=configuracoes"
            )
        return form_perfil, form_senha, None
    form_perfil = PerfilInstitucionalForm(request.POST, request.FILES, instance=request.user)
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
        return form_perfil, form_senha, redirect(
            f"{reverse('plataforma:institutional_profile')}?aba=configuracoes"
        )
    return form_perfil, form_senha, None


def _dados_projetos_perfil(organizacao, usuario):
    dados = {"meus_projetos": [], "projetos_institucionais": [], "inscricoes": [], "grupos_ativos": []}
    if not organizacao:
        return dados
    projetos = Project.objects.filter(organizacao=organizacao).select_related("owner").annotate(
        total_membros=Count("memberships", distinct=True), total_estrelas=Count("votes", distinct=True)
    )
    dados["meus_projetos"] = _decorar_projetos(list(projetos.filter(owner=usuario).order_by("-updated_at")))
    dados["projetos_institucionais"] = _decorar_projetos(list(
        projetos.filter(visibility=Project.VISIBILITY_PUBLIC)
        .exclude(Q(owner=usuario) | Q(memberships__user=usuario)).distinct()
        .order_by("-updated_at")[:6]
    ))
    dados["inscricoes"] = list(
        ProjectMember.objects.filter(
            project__visibility=Project.VISIBILITY_PUBLIC, user=usuario, project__organizacao=organizacao
        ).exclude(project__owner=usuario).select_related("project", "project__owner").order_by("-joined_at")
    )
    for inscricao in dados["inscricoes"]:
        _decorar_projetos([inscricao.project])
    dados["grupos_ativos"] = list(MembroGrupo.objects.filter(
        usuario=usuario, status=MembroGrupo.STATUS_ATIVO,
        grupo__turma__programa__organizacao=organizacao,
    ).select_related("grupo__turma__programa").order_by("grupo__nome"))
    return dados


def _dados_calendario_perfil(organizacao, usuario, request, ano, mes, hoje):
    eventos = list(EventoCalendario.objects.filter(
        organizacao=organizacao, aluno=usuario,
    ).select_related("projeto")) if organizacao else []
    eventos = visible_events(eventos, request)
    eventos_por_dia = {}
    for evento in eventos:
        eventos_por_dia.setdefault(evento.data, []).append(evento)
    semanas = []
    for semana in pycalendar.Calendar(firstweekday=0).monthdatescalendar(ano, mes):
        semanas.append([
            {
                "data": dia, "numero": dia.day, "fora_do_mes": dia.month != mes,
                "hoje": dia == hoje, "eventos": sorted(eventos_por_dia.get(dia, []), key=_chave_ordenacao),
            }
            for dia in semana
        ])
    proximas = sorted([evento for evento in eventos if evento.data >= hoje], key=_chave_ordenacao)[:3]
    primeiro = date(ano, mes, 1)
    anterior = (primeiro - timedelta(days=1)).replace(day=1)
    proximo = (primeiro + timedelta(days=32)).replace(day=1)
    return {
        "semanas": semanas, "proximas_atividades": proximas,
        "ano_anterior": anterior.year, "mes_anterior": anterior.month,
        "ano_proximo": proximo.year, "mes_proximo": proximo.month,
    }


@tenant_required
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
        if not 2 <= ano <= 9998:
            raise ValueError
    except (TypeError, ValueError):
        ano, mes = hoje.year, hoje.month
        primeiro_dia = date(ano, mes, 1)
    perfil_usuario, _ = MemberProfile.objects.get_or_create(user=request.user)
    form_perfil, form_senha, response = _processar_atualizacao_perfil(request, perfil_usuario)
    if response:
        return response
    dados = _dados_projetos_perfil(organizacao, request.user)
    calendario = _dados_calendario_perfil(organizacao, request.user, request, ano, mes, hoje)
    context.update({
        "nav_ativo": "perfil", "aba_ativa": aba_ativa,
        "form_perfil": form_perfil, "form_senha": form_senha, "perfil_usuario": perfil_usuario,
        **dados, "total_projetos": len(dados["meus_projetos"]),
        "total_institucionais": len(dados["projetos_institucionais"]),
        "total_inscricoes": len(dados["inscricoes"]),
        "total_concluidos": sum(p.status == Project.STATUS_DONE for p in dados["meus_projetos"]),
        "ano": ano, "mes": mes, "mes_nome": MESES[mes - 1], "hoje": hoje,
        **calendario, "inicial_usuario": (context["nome_usuario"] or "?")[:1].upper(),
    })
    return render(request, "institutional/experience/profile.html", context)

def _chave_ordenacao(evento):
    return (evento.data, evento.horario or time.min, evento.titulo)


def _filtrar_projetos_explorar(queryset, request, organizacao, busca, categoria, aluno_filtro):
    if busca:
        queryset = queryset.filter(
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
        queryset = queryset.filter(category__iexact=categoria)
    if aluno_filtro:
        queryset = queryset.filter(owner__username=aluno_filtro)
    if request.GET.get("status"):
        queryset = queryset.filter(status=request.GET["status"])
    if request.GET.get("tag"):
        queryset = queryset.filter(tags__icontains=request.GET["tag"])
    return queryset


def _filtrar_tipo_projetos_explorar(queryset, request, organizacao):
    tipo = request.GET.get("tipo", "")
    if tipo == "autonomo":
        return queryset.filter(vinculo_institucional__isnull=True)
    if tipo == "vinculado":
        from .models import ProgramaInstitucional

        return queryset.filter(
            vinculo_institucional__turma__programa__organizacao=organizacao,
            vinculo_institucional__turma__programa__status=ProgramaInstitucional.STATUS_PUBLICADO,
        )
    return queryset


def _projetos_explorar(request, organizacao, busca, categoria, aluno_filtro):
    from core.rankings import ranked_projects

    projetos = Project.objects.filter(
        organizacao=organizacao,
        visibility=Project.VISIBILITY_PUBLIC,
    ).select_related("owner").annotate(total_membros=Count("memberships", distinct=True))
    projetos = _filtrar_tipo_projetos_explorar(projetos, request, organizacao)
    total = projetos.count()
    projetos = _filtrar_projetos_explorar(
        projetos, request, organizacao, busca, categoria, aluno_filtro
    ).annotate(relevance=Count("votes", distinct=True))
    if request.GET.get("ordering", "recent") == "relevance":
        projetos = ranked_projects(projetos, tenant_id=organizacao.pk)
    else:
        projetos = projetos.order_by("-updated_at")
    page = Paginator(projetos, 24).get_page(request.GET.get("page"))
    return page, _decorar_projetos(list(page.object_list)), total


def _filtrar_membros_explorar(queryset, organizacao, busca, categoria):
    if busca:
        if busca.startswith("@"):
            queryset = queryset.filter(usuario__username__icontains=busca[1:])
        else:
            queryset = queryset.filter(
                Q(usuario__username__icontains=busca)
                | Q(usuario__first_name__icontains=busca)
                | Q(usuario__last_name__icontains=busca)
                | Q(
                    usuario__owned_projects__title__icontains=busca,
                    usuario__owned_projects__organizacao=organizacao,
                    usuario__owned_projects__visibility=Project.VISIBILITY_PUBLIC,
                )
                | Q(
                    usuario__owned_projects__category__icontains=busca,
                    usuario__owned_projects__organizacao=organizacao,
                    usuario__owned_projects__visibility=Project.VISIBILITY_PUBLIC,
                )
            ).distinct()
    if categoria:
        queryset = queryset.filter(
            usuario__owned_projects__category__iexact=categoria,
            usuario__owned_projects__organizacao=organizacao,
            usuario__owned_projects__visibility=Project.VISIBILITY_PUBLIC,
        ).distinct()
    return queryset


def _decorar_membros_explorar(membros):
    for membro in membros:
        membro.nome = _nome_usuario(membro.usuario)
        membro.inicial = membro.nome[:1].upper()
        membro.papel_rotulo = PAPEL_ROTULO.get(membro.papel, membro.get_papel_display())
        projetos = getattr(membro.usuario, "projetos_publicos", [])
        membro.total_projetos = len(projetos)
        membro.categorias = sorted({projeto.category for projeto in projetos if projeto.category})[:4]
    return membros


def _membros_explorar(request, organizacao, busca, categoria):
    membros = MembroOrganizacao.objects.filter(
        organizacao=organizacao,
        status=MembroOrganizacao.STATUS_ATIVA,
    ).exclude(usuario=request.user)
    total = membros.count()
    participacoes = ProjectMember.objects.filter(
        user=request.user,
        project__organizacao=organizacao,
    ).count()
    projetos_publicos = Project.objects.filter(
        organizacao=organizacao,
        visibility=Project.VISIBILITY_PUBLIC,
    ).only("id", "owner_id", "title", "category")
    membros = membros.select_related("usuario").prefetch_related(
        Prefetch("usuario__owned_projects", queryset=projetos_publicos, to_attr="projetos_publicos")
    )
    membros = _filtrar_membros_explorar(membros, organizacao, busca, categoria)
    page = Paginator(
        membros.order_by("usuario__first_name", "usuario__username"), 24
    ).get_page(request.GET.get("page"))
    return page, _decorar_membros_explorar(list(page.object_list)), total, participacoes


def _categorias_explorar(organizacao):
    return list(
        Project.objects.filter(
            organizacao=organizacao,
            visibility=Project.VISIBILITY_PUBLIC,
        )
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )



@tenant_required
@login_required
def explore(request):
    """Descobre projetos abertos a colaboração e alunos do ambiente."""
    context = _contexto_base(request)
    organizacao = context["organizacao"]

    vista = request.GET.get("vista", "projetos")
    if vista not in ("projetos", "alunos"):
        vista = "projetos"
    busca = (request.GET.get("q") or "").strip()
    categoria = (request.GET.get("category") or request.GET.get("categoria") or "").strip()
    aluno_filtro = (request.GET.get("aluno") or "").strip()

    page = people_page = None
    projetos_abertos = []
    colaboradores = []
    categorias = []
    aluno_filtro_nome = ""
    total_projetos_abertos = 0
    total_colaboradores = 0
    total_participacoes = 0

    if organizacao:
        page, projetos_abertos, total_projetos_abertos = _projetos_explorar(
            request, organizacao, busca, categoria, aluno_filtro
        )
        people_page, colaboradores, total_colaboradores, total_participacoes = _membros_explorar(
            request, organizacao, busca, "" if vista == "alunos" else categoria
        )
        categorias = _categorias_explorar(organizacao)

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
    params = request.GET.copy()
    params.pop("page", None)
    context["pagination_query"] = params.urlencode()
    context["page_obj"] = people_page if vista == "alunos" else page
    context["projects"] = projetos_abertos
    return render(request, "institutional/experience/explore.html", context)



@tenant_required
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
        return redirect("plataforma:institutional_profile")

    removidos, _ = ProjectMember.objects.filter(
        project=projeto,
        user=request.user,
    ).delete()
    if removidos:
        messages.success(request, f"Você saiu da colaboração do projeto “{projeto.title}”.")
    else:
        messages.info(request, "Você não participa deste projeto.")
    return redirect("plataforma:institutional_profile")



@tenant_required
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
    request.session[f"tenant:{request.organizacao.pk}:inbox_visto"] = timezone.now().isoformat()
    notifications = _notificacoes_tenant(request)
    notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
    context["notifications"] = notifications[:50]
    return render(request, "institutional/experience/inbox.html", context)



@login_required
@tenant_required
@require_safe
def notification_summary(request):
    try:
        with transaction.atomic():
            count = _contar_novas_inbox(request)
    except DatabaseError:
        logging.getLogger(__name__).warning("Resumo de notificações indisponível.")
        return JsonResponse({"count": None}, status=503)
    return JsonResponse({"count": count})
