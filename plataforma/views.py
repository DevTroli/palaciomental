import json
import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, Exists, OuterRef, Q, When
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.templatetags.static import static
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .health import deployment_metadata
from .forms import CollaborationRequestForm, CommentForm, ConviteGrupoForm, ConviteOrganizacaoForm, GrupoForm, IdentidadeOrganizacaoForm, MemberCreationForm, MilestoneForm, ProfileForm, ProgramaInstitucionalForm, ProjectBasicsForm, ProjectContextForm, ProjectForm, ProjectLinkFormSet, SolicitacaoGrupoForm, SolicitacaoTurmaForm, TurmaForm
from .models import CollaborationRequest, ConviteGrupo, ConviteOrganizacao, Grupo, IdentidadeOrganizacao, MemberProfile, MembroOrganizacao, MembroGrupo, MembroTurma, Notification, ProgramaInstitucional, Project, ProjectComment, ProjectLink, ProjectMember, ProjectMilestone, ProjectVote, SolicitacaoGrupo, SolicitacaoTurma, Turma, VinculoProjetoInstitucional
from .services import emitir_convite_organizacao, papeis_convidaveis
from .validators import CORES_SEMANTICAS
from .navigation import global_home_url as _global_home_url, project_notification_url
from .invitations import invitation_accept, invitation_login_target
from .invitation_delivery import deliver_invitation
from .management_metrics import management_distributions
from .branding import invitation_branding
from core.rankings import complete_ranking_ids


def _tenant_identity_context(organizacao):
    identidade = getattr(organizacao, "identidade", None)
    return {
        "organizacao": organizacao,
        "identidade": identidade,
    }


def register(request):
    if getattr(request, "organizacao", None) is not None:
        context = _tenant_identity_context(request.organizacao)
        context.update({"titulo": "Cadastro fechado", "mensagem": "Este ambiente institucional é privado e funciona somente por convite.", "global_home_url": _global_home_url(request)})
        return render(
            request,
            "institutional/access_denied.html",
            context,
            status=403,
        )
    if request.user.is_authenticated:
        return redirect("plataforma:profile", username=request.user.username)
    form = MemberCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        MemberProfile.objects.create(user=user)
        login(request, user)
        messages.success(request, "Conta criada. Agora você pode dar forma ao seu primeiro projeto.")
        return redirect("plataforma:profile", username=user.username)
    return render(request, "auth/register.html", {"form": form})


def _safe_local_next(request, value):
    """Aceita apenas caminho local ("/..."), nunca outro host ou esquema.

    Decisão aprovada: "next" aceita só caminho local, com fallback fixo.
    """
    value = (value or "").strip()
    if not value.startswith("/") or value.startswith(("//", "/\\")):
        return ""
    if not url_has_allowed_host_and_scheme(value, allowed_hosts=set(), require_https=request.is_secure()):
        return ""
    return value


def login_view(request):
    from django.contrib.auth.forms import AuthenticationForm
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        organizacao = getattr(request, "organizacao", None)
        if organizacao is not None:
            afiliacao = MembroOrganizacao.objects.filter(organizacao=organizacao, usuario=user, status=MembroOrganizacao.STATUS_ATIVA).first()
            if afiliacao is None:
                next_url = _safe_local_next(request, request.GET.get("next", ""))
                if next_url and invitation_login_target(request, next_url, user):
                    return redirect(next_url)
                context = _tenant_identity_context(organizacao)
                context.update({"titulo": "Acesso pendente", "mensagem": "Sua conta foi autenticada, mas ainda não possui um convite ou afiliação ativa neste ambiente.", "global_home_url": _global_home_url(request)})
                return render(
                    request,
                    "institutional/access_denied.html",
                    context,
                    status=403,
                )
            next_url = _safe_local_next(request, request.GET.get("next", ""))
            if next_url:
                if next_url.startswith("/gestao/") and afiliacao.papel not in {MembroOrganizacao.PAPEL_PROPRIETARIO, MembroOrganizacao.PAPEL_GESTOR}:
                    return redirect("core:index")
                return redirect(next_url)
            if afiliacao.papel in {MembroOrganizacao.PAPEL_PROPRIETARIO, MembroOrganizacao.PAPEL_GESTOR}:
                return redirect("plataforma:institutional_management")
            return redirect("core:index")
        next_url = _safe_local_next(request, request.GET.get("next", ""))
        if next_url:
            return redirect(next_url)
        return redirect("plataforma:projects")
    context: dict[str, object] = {"form": form}
    if getattr(request, "organizacao", None) is not None:
        context.update(_tenant_identity_context(request.organizacao))
        context["global_home_url"] = _global_home_url(request)
    template_name = "auth/institutional_login.html" if getattr(request, "organizacao", None) is not None else "auth/login.html"
    return render(request, template_name, context)


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect("core:index")


def profile(request, username):
    if getattr(request, "organizacao", None) and request.user.is_authenticated and username == request.user.username:
        from .experience import profile as institutional_profile
        return institutional_profile(request)
    user = get_object_or_404(User, username=username)
    MemberProfile.objects.get_or_create(user=user)
    project_scope = _project_scope(request).annotate(relevance=Count("votes", distinct=True))
    owned = project_scope.filter(owner=user)
    if request.user != user:
        owned = owned.filter(visibility=Project.VISIBILITY_PUBLIC)
    collaborated = project_scope.filter(memberships__user=user, visibility=Project.VISIBILITY_PUBLIC).exclude(owner=user).distinct()
    return render(request, "members/profile.html", {"member": user, "owned_projects": owned, "collaborated_projects": collaborated})


@login_required
def profile_edit(request):
    if getattr(request, "organizacao", None):
        return redirect(reverse("plataforma:institutional_profile") + "?aba=configuracoes")
    profile_obj, _ = MemberProfile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile_obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Seu perfil foi atualizado.")
        return redirect("plataforma:profile", username=request.user.username)
    return render(request, "members/profile_edit.html", {"form": form})


def projects(request):
    if getattr(request, "organizacao", None):
        from .experience import explore
        return explore(request)
    vote_exists = ProjectVote.objects.filter(project=OuterRef("pk"), user=request.user) if request.user.is_authenticated else ProjectVote.objects.none()
    queryset = _project_scope(request).filter(visibility=Project.VISIBILITY_PUBLIC).select_related("owner").annotate(relevance=Count("votes"), user_voted=Exists(vote_exists))
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    status = request.GET.get("status", "").strip()
    tag = request.GET.get("tag", "").strip()
    ordering = request.GET.get("ordering", "recent")
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(direction__icontains=query))
    if category:
        queryset = queryset.filter(category__iexact=category)
    if status:
        queryset = queryset.filter(status=status)
    if tag:
        queryset = queryset.filter(tags__icontains=tag)
    if ordering == "relevance":
        tenant_id = getattr(getattr(request, "organizacao", None), "pk", None)
        ranking_ids = complete_ranking_ids(tenant_id=tenant_id)
        if ranking_ids:
            ranking_order = Case(
                *[When(pk=project_id, then=position) for position, project_id in enumerate(ranking_ids)],
                default=len(ranking_ids),
            )
            queryset = queryset.order_by(ranking_order, "-relevance", "-updated_at", "-pk")
        else:
            queryset = queryset.order_by("-relevance", "-updated_at", "-pk")
    categories = _project_scope(request).filter(visibility=Project.VISIBILITY_PUBLIC).values_list("category", flat=True).distinct().order_by("category")
    organizacao = getattr(request, "organizacao", None)
    context = {
        "projects": queryset,
        "categories": categories,
        "statuses": Project.STATUS_CHOICES,
        "filters": {"q": query, "category": category, "status": status, "tag": tag, "ordering": ordering},
        "catalog_context": "institutional" if organizacao else "global",
        "catalog_name": organizacao.nome if organizacao else "Palácio Mental",
    }
    return render(request, "projects/list.html", context)


@login_required
def institutional_management(request):
    """Portal de gestão do tenant; nunca expõe o Django Admin interno do PM."""
    organizacao = getattr(request, "organizacao", None)
    afiliacao = getattr(request, "membro_organizacao", None)
    if organizacao is None or afiliacao is None:
        raise Http404
    if afiliacao.papel not in {
        MembroOrganizacao.PAPEL_PROPRIETARIO,
        MembroOrganizacao.PAPEL_GESTOR,
    }:
        return JsonResponse({"detail": "Seu papel não possui acesso à gestão institucional."}, status=403)
    identidade = getattr(organizacao, "identidade", None)
    context = {
        "organizacao": organizacao,
        "afiliacao": afiliacao,
        "identidade": identidade,
        "metricas": {
            "membros": organizacao.afiliacoes.filter(status=MembroOrganizacao.STATUS_ATIVA).count(),
            "convites": organizacao.convites.filter(status=ConviteOrganizacao.STATUS_PENDENTE, expira_em__gt=timezone.now()).count(),
            "programas": organizacao.programas.filter(status=ProgramaInstitucional.STATUS_PUBLICADO).count(),
            "projetos": organizacao.projetos.count(),
        },
        "programas_rascunho": organizacao.programas.filter(status=ProgramaInstitucional.STATUS_RASCUNHO).order_by("-atualizado_em")[:5],
    }
    distributions = management_distributions(organizacao)
    context["management_charts"] = distributions
    context["project_status_rows"] = list(zip(distributions["projects"]["labels"], distributions["projects"]["values"]))
    context["member_role_rows"] = list(zip(distributions["members"]["labels"], distributions["members"]["values"]))
    from .experience import _decorar_projetos, _nome_usuario
    context["nav_ativo"] = "gestao"
    context["total_alunos"] = context["metricas"]["membros"]
    context["total_projetos"] = context["metricas"]["projetos"]
    context["total_abertos"] = organizacao.projetos.filter(visibility=Project.VISIBILITY_PUBLIC, seeking_collaborators=True).count()
    context["projetos"] = _decorar_projetos(list(organizacao.projetos.filter(visibility=Project.VISIBILITY_PUBLIC).select_related("owner").annotate(total_membros=Count("memberships", distinct=True)).order_by("-updated_at")[:25]))
    context["membros"] = list(organizacao.afiliacoes.filter(status=MembroOrganizacao.STATUS_ATIVA).select_related("usuario").order_by("usuario__username")[:50])
    for member in context["membros"]:
        member.nome = _nome_usuario(member.usuario)
        member.inicial = member.nome[:1].upper()
        member.papel_rotulo = member.get_papel_display()
    context["grupos_sem_professor"] = Grupo.objects.filter(
        turma__programa__organizacao=organizacao,
        turma__programa__status=ProgramaInstitucional.STATUS_PUBLICADO,
        status=Grupo.STATUS_ATIVO,
        turma__professor_responsavel__isnull=True,
    ).select_related("turma__programa")[:5]
    return render(
        request,
        "institutional/management.html",
        context,
    )


@login_required
def institutional_identity(request):
    organizacao = getattr(request, "organizacao", None)
    afiliacao = getattr(request, "membro_organizacao", None)
    if organizacao is None or afiliacao is None or afiliacao.papel not in {MembroOrganizacao.PAPEL_PROPRIETARIO, MembroOrganizacao.PAPEL_GESTOR}:
        return JsonResponse({"detail": "Somente proprietários e gestores podem editar a identidade institucional."}, status=403)
    identidade, _ = IdentidadeOrganizacao.objects.get_or_create(organizacao=organizacao, defaults={"nome_exibicao": organizacao.nome})
    form = IdentidadeOrganizacaoForm(request.POST or None, request.FILES or None, instance=identidade)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Identidade institucional atualizada.")
        return redirect("plataforma:institutional_identity")
    context = _tenant_identity_context(organizacao)
    context.update({"afiliacao": afiliacao, "form": form, "paleta": CORES_SEMANTICAS})
    return render(request, "institutional/identity.html", context)


def _ultimo_proprietario_ativo(organizacao, membro):
    return (
        membro.papel == MembroOrganizacao.PAPEL_PROPRIETARIO
        and organizacao.afiliacoes.filter(
            papel=MembroOrganizacao.PAPEL_PROPRIETARIO, status=MembroOrganizacao.STATUS_ATIVA
        ).count() <= 1
    )


def _convidar_membro(request, organizacao, afiliacao, papeis):
    """Retorna (form, response). response só existe quando o convite foi criado."""
    form = ConviteOrganizacaoForm(request.POST, papeis_permitidos=papeis)
    if not form.is_valid():
        return form, None
    try:
        convite, raw_token = emitir_convite_organizacao(
            organizacao, afiliacao, form.cleaned_data["email"], form.cleaned_data["papel"]
        )
    except ValidationError as exc:
        form.add_error(None, exc.message)
        return form, None
    transaction.on_commit(
        lambda: deliver_invitation(request, _send_organization_invitation_email, convite, raw_token)
    )
    return form, redirect("plataforma:institutional_members")


def _alterar_status_membro(request, organizacao, membro, acao):
    if acao in {"suspender", "remover"}:
        if membro.usuario_id == request.user.pk:
            return JsonResponse({"detail": "Você não pode remover ou suspender sua própria afiliação."}, status=400)
        if _ultimo_proprietario_ativo(organizacao, membro):
            return JsonResponse({"detail": "A organização precisa manter pelo menos um proprietário ativo."}, status=400)
        membro.status = MembroOrganizacao.STATUS_SUSPENSA
        membro.save(update_fields=["status"])
        messages.success(request, "Afiliação suspensa.")
    else:
        membro.status = MembroOrganizacao.STATUS_ATIVA
        membro.save(update_fields=["status"])
        messages.success(request, "Afiliação reativada.")
    return None


def _alterar_papel_membro(request, organizacao, membro):
    if request.membro_organizacao.papel != MembroOrganizacao.PAPEL_PROPRIETARIO:
        return JsonResponse({"detail": "Somente o proprietário pode alterar papéis."}, status=403)
    novo_papel = request.POST.get("papel")
    if novo_papel not in dict(MembroOrganizacao.PAPEL_CHOICES):
        return JsonResponse({"detail": "Papel institucional inválido."}, status=400)
    if novo_papel == MembroOrganizacao.PAPEL_PROPRIETARIO and request.membro_organizacao.papel != MembroOrganizacao.PAPEL_PROPRIETARIO:
        return JsonResponse({"detail": "Somente o proprietário pode conceder o papel de proprietário."}, status=403)
    if novo_papel != MembroOrganizacao.PAPEL_PROPRIETARIO and _ultimo_proprietario_ativo(organizacao, membro):
        return JsonResponse({"detail": "A organização precisa manter pelo menos um proprietário ativo."}, status=400)
    membro.papel = novo_papel
    membro.save(update_fields=["papel"])
    messages.success(request, "Papel institucional atualizado.")
    return None


def _gerenciar_membro(request, organizacao):
    # Serialize owner changes for this organization, including changes to
    # different members, so concurrent requests cannot remove both owners.
    with transaction.atomic():
        type(organizacao).objects.select_for_update().get(pk=organizacao.pk)
        return _gerenciar_membro_locked(request, organizacao)


def _gerenciar_membro_locked(request, organizacao):
    membro = get_object_or_404(MembroOrganizacao, pk=request.POST.get("membro_id"), organizacao=organizacao)
    acao = request.POST.get("acao")
    if membro.papel == MembroOrganizacao.PAPEL_PROPRIETARIO and request.membro_organizacao.papel != MembroOrganizacao.PAPEL_PROPRIETARIO:
        return JsonResponse({"detail": "Apenas o proprietário pode alterar outro proprietário."}, status=403)
    if acao in {"suspender", "remover", "ativar"}:
        erro = _alterar_status_membro(request, organizacao, membro, acao)
    elif acao == "papel":
        erro = _alterar_papel_membro(request, organizacao, membro)
    else:
        erro = None
    return erro or redirect("plataforma:institutional_members")


@login_required
def institutional_members(request):
    organizacao = getattr(request, "organizacao", None)
    afiliacao = getattr(request, "membro_organizacao", None)
    if organizacao is None or afiliacao is None or not _can_manage_affiliations(request):
        return JsonResponse({"detail": "Você não pode administrar afiliações neste ambiente."}, status=403)
    papeis = papeis_convidaveis(afiliacao.papel)
    convite_form = None
    if request.method == "POST" and request.POST.get("acao") == "convidar":
        convite_form, response = _convidar_membro(request, organizacao, afiliacao, papeis)
        if response is not None:
            return response
    elif request.method == "POST":
        return _gerenciar_membro(request, organizacao)
    if convite_form is None:
        convite_form = ConviteOrganizacaoForm(papeis_permitidos=papeis)
    afiliacoes = organizacao.afiliacoes.select_related("usuario")
    papel_filtro = request.GET.get("papel", "")
    if papel_filtro not in dict(MembroOrganizacao.PAPEL_CHOICES):
        papel_filtro = ""
    membros = afiliacoes.filter(papel=papel_filtro) if papel_filtro else afiliacoes
    membros = Paginator(membros.order_by("usuario__username", "pk"), 12).get_page(request.GET.get("pagina"))
    contagens = dict(afiliacoes.order_by().values_list("papel").annotate(total=Count("pk")))
    filtros_papeis = [(value, label, contagens.get(value, 0)) for value, label in MembroOrganizacao.PAPEL_CHOICES]
    convites = organizacao.convites.filter(status=ConviteOrganizacao.STATUS_PENDENTE, expira_em__gt=timezone.now()).select_related("convidado_por").order_by("expira_em")
    return render(request, "institutional/members.html", {"organizacao": organizacao, "identidade": getattr(organizacao, "identidade", None), "membros": membros, "papeis": MembroOrganizacao.PAPEL_CHOICES, "convite_form": convite_form, "convites": convites, "papeis_convidaveis": papeis, "papel_filtro": papel_filtro, "filtros_papeis": filtros_papeis, "total_afiliacoes": sum(contagens.values())})


def _can_manage_institutional_structure(request):
    afiliacao = getattr(request, "membro_organizacao", None)
    return afiliacao and afiliacao.papel in {
        MembroOrganizacao.PAPEL_PROPRIETARIO,
        MembroOrganizacao.PAPEL_GESTOR,
    }


def _can_manage_affiliations(request):
    return _can_manage_institutional_structure(request)


def _send_organization_invitation_email(request, convite, raw_token):
    invite_url = request.build_absolute_uri(reverse("plataforma:institutional_organization_invite_accept", kwargs={"token": raw_token}))
    contexto = {
        "convite": convite,
        "organizacao": convite.organizacao,
        "identidade": getattr(convite.organizacao, "identidade", None),
        "convidado_por": convite.convidado_por,
        "invite_url": invite_url,
        **invitation_branding(request, convite.organizacao),
    }
    email = EmailMultiAlternatives(
        subject=f"Convite para entrar em {convite.organizacao.nome}",
        body=render_to_string("emails/organization_invitation.txt", contexto),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[convite.email],
        headers={"Idempotency-Key": f"organization-invitation/{convite.pk}"},
    )
    email.attach_alternative(render_to_string("emails/organization_invitation.html", contexto), "text/html")
    email.send(fail_silently=False)


def _is_active_group_member(request, group):
    afiliacao = getattr(request, "membro_organizacao", None)
    return bool(afiliacao and afiliacao.papel == MembroOrganizacao.PAPEL_MEMBRO
        and group.turma.status == Turma.STATUS_ATIVO
        and group.turma.programa.status == ProgramaInstitucional.STATUS_PUBLICADO
        and MembroTurma.objects.filter(turma=group.turma, usuario=request.user, status=MembroTurma.STATUS_ATIVO).exists()
        and group.membros.filter(usuario=request.user, status=MembroGrupo.STATUS_ATIVO).exists())


def _usuario_tem_grupo_ativo_na_turma(usuario, turma, *, excluir_grupo=None):
    """Uma pessoa só pode estar em um grupo ativo dentro da mesma turma."""
    if usuario is None:
        return False
    grupos = MembroGrupo.objects.filter(
        usuario=usuario,
        grupo__turma=turma,
        status=MembroGrupo.STATUS_ATIVO,
        grupo__status=Grupo.STATUS_ATIVO,
    )
    if excluir_grupo is not None:
        grupos = grupos.exclude(grupo=excluir_grupo)
    return grupos.exists()


def _notificar(usuario, kind, message, url):
    if usuario and usuario.pk:
        Notification.objects.create(recipient=usuario, kind=kind, message=message[:280], url=url)


def _is_active_group_representative(request, group):
    return _is_active_group_member(request, group) and group.membros.filter(usuario=request.user, representante=True, status=MembroGrupo.STATUS_ATIVO).exists()


def _can_invite_to_group(request, group):
    afiliacao = getattr(request, "membro_organizacao", None)
    if afiliacao is None:
        return False
    return group.status == Grupo.STATUS_ATIVO and _is_active_group_member(request, group)


def _can_decide_group(request, group):
    return _is_active_group_representative(request, group) or _can_manage_class(request, group.turma)


def _can_view_group(request, group):
    afiliacao = getattr(request, "membro_organizacao", None)
    if afiliacao is None:
        return False
    if afiliacao.papel in {MembroOrganizacao.PAPEL_PROPRIETARIO, MembroOrganizacao.PAPEL_GESTOR}:
        return True
    if afiliacao.papel == MembroOrganizacao.PAPEL_PROFESSOR and group.turma.professor_responsavel_id == request.user.pk:
        return True
    return afiliacao.papel == MembroOrganizacao.PAPEL_MEMBRO and (
        group.membros.filter(usuario=request.user, status=MembroGrupo.STATUS_ATIVO).exists()
        or MembroTurma.objects.filter(turma=group.turma, usuario=request.user, status=MembroTurma.STATUS_ATIVO).exists()
    )


def _can_manage_class(request, turma):
    afiliacao = getattr(request, "membro_organizacao", None)
    if afiliacao is None:
        return False
    return afiliacao.papel in {MembroOrganizacao.PAPEL_PROPRIETARIO, MembroOrganizacao.PAPEL_GESTOR} or (afiliacao.papel == MembroOrganizacao.PAPEL_PROFESSOR and turma.professor_responsavel_id == request.user.pk)


def _can_view_class(request, turma):
    afiliacao = getattr(request, "membro_organizacao", None)
    if afiliacao is None:
        return False
    if _can_manage_class(request, turma):
        return True
    if MembroTurma.objects.filter(turma=turma, usuario=request.user, status=MembroTurma.STATUS_ATIVO).exists():
        return True
    return turma.politica_participacao in {Turma.POLITICA_ABERTA, Turma.POLITICA_APROVACAO} and turma.status == Turma.STATUS_ATIVO


def _visible_programs(request):
    programas = ProgramaInstitucional.objects.filter(organizacao=request.organizacao)
    if _can_manage_institutional_structure(request):
        return programas
    if request.membro_organizacao.papel == MembroOrganizacao.PAPEL_PROFESSOR:
        return programas.filter(Q(status=ProgramaInstitucional.STATUS_PUBLICADO) | Q(turmas__professor_responsavel=request.user)).distinct()
    return programas.filter(status=ProgramaInstitucional.STATUS_PUBLICADO)


def _send_group_invitation_email(request, convite, raw_token):
    invite_url = request.build_absolute_uri(reverse("plataforma:institutional_invite_accept", kwargs={"token": raw_token}))
    grupo = convite.grupo
    contexto = {
        "convite": convite,
        "grupo": grupo,
        "programa": grupo.turma.programa,
        "organizacao": grupo.turma.programa.organizacao,
        "identidade": getattr(grupo.turma.programa.organizacao, "identidade", None),
        "convidado_por": convite.convidado_por,
        "invite_url": invite_url,
        **invitation_branding(request, grupo.turma.programa.organizacao),
    }
    email = EmailMultiAlternatives(
        subject=f"Convite para participar de {grupo.nome}",
        body=render_to_string("emails/institutional_invitation.txt", contexto),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[convite.email],
        headers={"Idempotency-Key": f"group-invitation/{convite.pk}"},
    )
    email.attach_alternative(render_to_string("emails/institutional_invitation.html", contexto), "text/html")
    email.send(fail_silently=False)


@login_required
def institutional_programs(request):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or getattr(request, "membro_organizacao", None) is None:
        raise Http404
    form = ProgramaInstitucionalForm(request.POST or None)
    if request.method == "POST":
        if not _can_manage_institutional_structure(request):
            return JsonResponse({"detail": "Seu papel não pode criar programas."}, status=403)
        if form.is_valid():
            programa = form.save(commit=False)
            programa.organizacao = organizacao
            programa.criado_por = request.user
            programa.slug = slugify(programa.nome)
            if ProgramaInstitucional.objects.filter(organizacao=organizacao, slug=programa.slug).exists():
                form.add_error("nome", "Já existe um programa com este nome nesta organização.")
            else:
                programa.save()
                messages.success(request, "Programa criado. Agora você pode adicionar uma turma.")
                return redirect("plataforma:institutional_program_detail", programa_id=programa.pk)
        return render(request, "institutional/program_create.html", {"organizacao": organizacao, "form": form, "nav_ativo": "turmas_e_equipes"})
    programas = _visible_programs(request).annotate(total_turmas=Count("turmas", distinct=True))
    return render(
        request,
        "institutional/programs.html",
        {"organizacao": organizacao, "programas": programas, "form": form, "pode_gerenciar": _can_manage_institutional_structure(request), "nav_ativo": "turmas_e_equipes"},
    )


@login_required
@require_http_methods(["GET", "POST"])
def institutional_program_create(request):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or not _can_manage_institutional_structure(request):
        return HttpResponseForbidden("Apenas a gestão pode criar programas.")
    if request.method == "POST":
        return institutional_programs(request)
    return render(request, "institutional/program_create.html", {"organizacao": organizacao, "form": ProgramaInstitucionalForm(), "nav_ativo": "turmas_e_equipes"})


@login_required
def institutional_program_detail(request, programa_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or getattr(request, "membro_organizacao", None) is None:
        raise Http404
    programa = get_object_or_404(_visible_programs(request), pk=programa_id)
    turmas = programa.turmas.prefetch_related("grupos").annotate(
        solicitacoes_pendentes=Count("solicitacoes", filter=Q(solicitacoes__status=SolicitacaoTurma.STATUS_PENDENTE))
    ).all()
    turmas = [turma for turma in turmas if _can_view_class(request, turma)]
    gerenciaveis = [turma for turma in turmas if _can_manage_class(request, turma)]
    participacoes = set(MembroTurma.objects.filter(turma__in=turmas, usuario=request.user, status=MembroTurma.STATUS_ATIVO).values_list("turma_id", flat=True))
    turmas_suspensas = set(MembroTurma.objects.filter(turma__in=turmas, usuario=request.user, status=MembroTurma.STATUS_SUSPENSO).values_list("turma_id", flat=True))
    grupos_membro = set(MembroGrupo.objects.filter(grupo__turma__in=turmas, usuario=request.user, status=MembroGrupo.STATUS_ATIVO).values_list("grupo_id", flat=True))
    grupos_suspensos = set(MembroGrupo.objects.filter(grupo__turma__in=turmas, usuario=request.user, status=MembroGrupo.STATUS_SUSPENSO).values_list("grupo_id", flat=True))
    pedidos_turma = set(SolicitacaoTurma.objects.filter(turma__in=turmas, usuario=request.user, status=SolicitacaoTurma.STATUS_PENDENTE).values_list("turma_id", flat=True))
    pedidos_grupo = set(SolicitacaoGrupo.objects.filter(grupo__turma__in=turmas, usuario=request.user, status=SolicitacaoGrupo.STATUS_PENDENTE).values_list("grupo_id", flat=True))
    aluno = request.membro_organizacao.papel == MembroOrganizacao.PAPEL_MEMBRO
    for turma in turmas:
        turma.e_membro = turma.pk in participacoes
        turma.suspenso = turma.pk in turmas_suspensas
        turma.pedido_pendente = turma.pk in pedidos_turma
        turma.pode_criar_grupo = aluno and turma.e_membro and turma.status == Turma.STATUS_ATIVO and programa.status == ProgramaInstitucional.STATUS_PUBLICADO
        for grupo in turma.grupos.all():
            grupo.e_membro = grupo.pk in grupos_membro
            grupo.suspenso = grupo.pk in grupos_suspensos
            grupo.pedido_pendente = grupo.pk in pedidos_grupo
            grupo.pode_ver = grupo.e_membro or turma in gerenciaveis or turma.e_membro
            grupo.pode_excluir = grupo.criado_por_id == request.user.pk
    solicitacoes = SolicitacaoTurma.objects.filter(turma__in=gerenciaveis, status=SolicitacaoTurma.STATUS_PENDENTE).select_related("usuario", "turma")
    return render(
        request,
        "institutional/program_detail.html",
        {"organizacao": organizacao, "programa": programa, "turmas": turmas, "solicitacoes": solicitacoes, "pode_gerenciar": _can_manage_institutional_structure(request), "aluno": aluno, "nav_ativo": "turmas_e_equipes"},
    )


@login_required
@require_http_methods(["POST"])
def institutional_class_participate(request, turma_id):
    organizacao = getattr(request, "organizacao", None)
    turma = get_object_or_404(Turma, pk=turma_id, programa__organizacao=organizacao)
    afiliacao = getattr(request, "membro_organizacao", None)
    if afiliacao is None:
        return JsonResponse({"detail": "Você precisa estar afiliado a este ambiente."}, status=403)
    if afiliacao.papel != MembroOrganizacao.PAPEL_MEMBRO or turma.programa.status != ProgramaInstitucional.STATUS_PUBLICADO:
        return JsonResponse({"detail": "A participação está disponível para alunos em programas publicados."}, status=403)
    if turma.status == Turma.STATUS_ENCERRADO or turma.politica_participacao == Turma.POLITICA_ENCERRADA:
        return JsonResponse({"detail": "Esta turma está encerrada."}, status=403)
    if MembroTurma.objects.filter(turma=turma, usuario=request.user, status=MembroTurma.STATUS_ATIVO).exists():
        return redirect("plataforma:institutional_program_detail", programa_id=turma.programa_id)
    if MembroTurma.objects.filter(turma=turma, usuario=request.user, status=MembroTurma.STATUS_SUSPENSO).exists():
        return JsonResponse({"detail": "Sua participação nesta turma está suspensa."}, status=403)
    if turma.politica_participacao == Turma.POLITICA_CONVITE:
        return JsonResponse({"detail": "Esta turma aceita apenas convites."}, status=403)
    form = SolicitacaoTurmaForm(request.POST or None)
    if turma.politica_participacao == Turma.POLITICA_ABERTA:
        MembroTurma.objects.get_or_create(turma=turma, usuario=request.user)
        messages.success(request, "Você entrou na turma.")
    elif form.is_valid():
        SolicitacaoTurma.objects.update_or_create(
            turma=turma,
            usuario=request.user,
            status=SolicitacaoTurma.STATUS_PENDENTE,
            defaults={"mensagem": form.cleaned_data["mensagem"]},
        )
        gestores = MembroOrganizacao.objects.filter(
            organizacao=organizacao,
            papel__in=[MembroOrganizacao.PAPEL_PROPRIETARIO, MembroOrganizacao.PAPEL_GESTOR],
            status=MembroOrganizacao.STATUS_ATIVA,
        ).select_related("usuario")
        for gestor in gestores:
            _notificar(gestor.usuario, "class_join_request", f"@{request.user.username} pediu para entrar em {turma.nome}.", request.build_absolute_uri(reverse("plataforma:institutional_program_detail", args=[turma.programa_id])))
        messages.success(request, "Sua solicitação foi enviada para aprovação.")
    else:
        return render(request, "institutional/class_request.html", {"organizacao": organizacao, "turma": turma, "form": form})
    return redirect("plataforma:institutional_program_detail", programa_id=turma.programa_id)


@login_required
@require_http_methods(["POST"])
def institutional_class_request_decide(request, request_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None:
        raise Http404
    solicitacao = get_object_or_404(
        SolicitacaoTurma.objects.select_related("turma__programa__organizacao"),
        pk=request_id,
        turma__programa__organizacao=organizacao,
    )
    if not _can_manage_class(request, solicitacao.turma):
        return JsonResponse({"detail": "Você não pode decidir solicitações desta turma."}, status=403)
    if solicitacao.status != SolicitacaoTurma.STATUS_PENDENTE:
        return JsonResponse({"detail": "Esta solicitação já foi decidida."}, status=400)
    if request.POST.get("acao") not in {"aprovar", "recusar"}:
        return JsonResponse({"detail": "Ação inválida."}, status=400)
    if request.POST.get("acao") == "aprovar":
        if not MembroOrganizacao.objects.filter(organizacao=organizacao, usuario=solicitacao.usuario, papel=MembroOrganizacao.PAPEL_MEMBRO, status=MembroOrganizacao.STATUS_ATIVA).exists():
            return JsonResponse({"detail": "O solicitante precisa ser um aluno ativo."}, status=403)
        if MembroTurma.objects.filter(turma=solicitacao.turma, usuario=solicitacao.usuario, status=MembroTurma.STATUS_SUSPENSO).exists():
            return JsonResponse({"detail": "A participação nesta turma está suspensa."}, status=403)
        MembroTurma.objects.update_or_create(turma=solicitacao.turma, usuario=solicitacao.usuario, defaults={"status": MembroTurma.STATUS_ATIVO})
        solicitacao.status = SolicitacaoTurma.STATUS_APROVADA
    else:
        solicitacao.status = SolicitacaoTurma.STATUS_RECUSADA
    solicitacao.decidido_por = request.user
    solicitacao.decidido_em = timezone.now()
    solicitacao.save(update_fields=["status", "decidido_por", "decidido_em"])
    _notificar(solicitacao.usuario, "class_request_decision", f"Seu pedido para entrar em {solicitacao.turma.nome} foi {'aprovado' if solicitacao.status == SolicitacaoTurma.STATUS_APROVADA else 'recusado'}.", request.build_absolute_uri(reverse("plataforma:institutional_program_detail", args=[solicitacao.turma.programa_id])))
    messages.success(request, "Solicitação atualizada.")
    return redirect("plataforma:institutional_program_detail", programa_id=solicitacao.turma.programa_id)


@login_required
def institutional_class_create(request, programa_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or not _can_manage_institutional_structure(request):
        return JsonResponse({"detail": "Você não pode criar turmas neste ambiente."}, status=403)
    programa = get_object_or_404(ProgramaInstitucional, pk=programa_id, organizacao=organizacao)
    form = TurmaForm(request.POST or None, organizacao=organizacao)
    if request.method == "POST" and form.is_valid():
        turma = form.save(commit=False)
        turma.programa = programa
        turma.criado_por = request.user
        if Turma.objects.filter(programa=programa, nome__iexact=turma.nome).exists():
            form.add_error("nome", "Já existe uma turma com este nome neste programa.")
        else:
            turma.save()
            messages.success(request, "Turma criada. Agora você pode abrir grupos dentro dela.")
            return redirect("plataforma:institutional_program_detail", programa_id=programa.pk)
    return render(request, "institutional/class_form.html", {"organizacao": organizacao, "programa": programa, "form": form, "nav_ativo": "turmas_e_equipes"})


@login_required
def institutional_program_edit(request, programa_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or not _can_manage_institutional_structure(request):
        return HttpResponseForbidden("Apenas a gestão pode editar programas.")
    programa = get_object_or_404(ProgramaInstitucional, pk=programa_id, organizacao=organizacao)
    form = ProgramaInstitucionalForm(request.POST or None, instance=programa)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Programa atualizado.")
        return redirect("plataforma:institutional_program_detail", programa_id=programa.pk)
    return render(request, "institutional/structure_form.html", {"organizacao": organizacao, "programa": programa, "form": form, "titulo": "Editar programa", "nav_ativo": "turmas_e_equipes"})


@login_required
def institutional_class_edit(request, turma_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or not _can_manage_institutional_structure(request):
        return HttpResponseForbidden("Apenas a gestão pode editar turmas.")
    turma = get_object_or_404(Turma, pk=turma_id, programa__organizacao=organizacao)
    form = TurmaForm(request.POST or None, instance=turma, organizacao=organizacao)
    if request.method == "POST" and form.is_valid():
        if Turma.objects.filter(programa=turma.programa, nome__iexact=form.cleaned_data["nome"]).exclude(pk=turma.pk).exists():
            form.add_error("nome", "Já existe uma turma com este nome neste programa.")
        else:
            form.save()
            messages.success(request, "Turma atualizada.")
            return redirect("plataforma:institutional_program_detail", programa_id=turma.programa_id)
    return render(request, "institutional/structure_form.html", {"organizacao": organizacao, "programa": turma.programa, "form": form, "titulo": "Editar turma", "nav_ativo": "turmas_e_equipes"})


def _delete_institutional_structure(request, kind, pk):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or (kind != "grupo" and not _can_manage_institutional_structure(request)):
        return HttpResponseForbidden("Você não pode excluir esta estrutura.")
    if kind == "programa":
        objeto = get_object_or_404(ProgramaInstitucional, pk=pk, organizacao=organizacao)
        vinculos = VinculoProjetoInstitucional.objects.filter(turma__programa=objeto)
        turmas_impactadas = Turma.objects.filter(programa=objeto)
        grupos_impactados = Grupo.objects.filter(turma__programa=objeto)
        destino = "plataforma:institutional_programs"
        destino_kwargs = {}
    elif kind == "turma":
        objeto = get_object_or_404(Turma, pk=pk, programa__organizacao=organizacao)
        vinculos = VinculoProjetoInstitucional.objects.filter(turma=objeto)
        turmas_impactadas = Turma.objects.filter(pk=objeto.pk)
        grupos_impactados = Grupo.objects.filter(turma=objeto)
        destino = "plataforma:institutional_program_detail"
        destino_kwargs = {"programa_id": objeto.programa_id}
    else:
        objeto = get_object_or_404(Grupo, pk=pk, turma__programa__organizacao=organizacao)
        afiliacao = getattr(request, "membro_organizacao", None)
        if not afiliacao or objeto.criado_por_id != request.user.pk:
            return HttpResponseForbidden("Somente o autor pode excluir este grupo.")
        vinculos = VinculoProjetoInstitucional.objects.filter(grupo=objeto)
        turmas_impactadas = Turma.objects.none()
        grupos_impactados = Grupo.objects.filter(pk=objeto.pk)
        destino = "plataforma:institutional_program_detail"
        destino_kwargs = {"programa_id": objeto.turma.programa_id}
    def motivo_bloqueio():
        if vinculos.exists():
            return "Existem projetos vinculados. Altere ou remova os vínculos institucionais antes de excluir."
        if kind == "programa" and turmas_impactadas.exists():
            return "Este programa ainda tem turmas. Exclua as turmas antes de excluir o programa."
        if kind == "turma" and grupos_impactados.exists():
            return "Esta turma ainda tem grupos. Cada grupo deve ser excluído pelo seu autor antes de excluir a turma."
        return ""

    motivo = motivo_bloqueio()
    if request.method == "POST":
        with transaction.atomic():
            objeto = type(objeto).objects.select_for_update().get(pk=objeto.pk)
            if kind == "programa":
                list(Turma.objects.select_for_update().filter(programa=objeto))
                list(Grupo.objects.select_for_update().filter(turma__programa=objeto))
            elif kind == "turma":
                list(Grupo.objects.select_for_update().filter(turma=objeto))
            motivo = motivo_bloqueio()
            if not motivo:
                objeto.delete()
                messages.success(request, "Exclusão concluída.")
                return redirect(destino, **destino_kwargs)
    impacto = {"turmas": turmas_impactadas.count(), "grupos": grupos_impactados.count(), "participacoes_turma": MembroTurma.objects.filter(turma__in=turmas_impactadas).count(), "participacoes_grupo": MembroGrupo.objects.filter(grupo__in=grupos_impactados).count()}
    return render(request, "institutional/structure_delete.html", {"objeto": objeto, "tipo": kind, "bloqueado": bool(motivo), "motivo_bloqueio": motivo, "impacto": impacto, "cancelar": reverse(destino, kwargs=destino_kwargs), "nav_ativo": "turmas_e_equipes"}, status=409 if request.method == "POST" and motivo else 200)


@login_required
@require_http_methods(["GET", "POST"])
def institutional_program_delete(request, programa_id):
    return _delete_institutional_structure(request, "programa", programa_id)


@login_required
@require_http_methods(["GET", "POST"])
def institutional_class_delete(request, turma_id):
    return _delete_institutional_structure(request, "turma", turma_id)


@login_required
@require_http_methods(["GET", "POST"])
def institutional_group_delete(request, group_id):
    return _delete_institutional_structure(request, "grupo", group_id)


@login_required
def institutional_group_create_for_class(request, turma_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None:
        return JsonResponse({"detail": "Ambiente institucional inválido."}, status=403)
    turma = get_object_or_404(Turma, pk=turma_id, programa__organizacao=organizacao)
    afiliacao = getattr(request, "membro_organizacao", None)
    membro_elegivel = afiliacao is not None and afiliacao.papel == MembroOrganizacao.PAPEL_MEMBRO and MembroTurma.objects.filter(turma=turma, usuario=request.user, status=MembroTurma.STATUS_ATIVO).exists()
    pode_criar = membro_elegivel and turma.status == Turma.STATUS_ATIVO and turma.programa.status == ProgramaInstitucional.STATUS_PUBLICADO
    if not pode_criar:
        return JsonResponse({"detail": "Você não pode criar grupos nesta turma."}, status=403)
    form = GrupoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if _usuario_tem_grupo_ativo_na_turma(request.user, turma):
            form.add_error(None, "Você já participa de um grupo nesta turma. Saia dele antes de criar outro.")
            return render(request, "institutional/group_form.html", {"organizacao": organizacao, "programa": turma.programa, "turma": turma, "form": form, "nav_ativo": "turmas_e_equipes"})
        grupo = form.save(commit=False)
        grupo.turma = turma
        grupo.criado_por = request.user
        if Grupo.objects.filter(turma=turma, nome__iexact=grupo.nome).exists():
            form.add_error("nome", "Já existe um grupo com este nome nesta turma.")
        else:
            with transaction.atomic():
                grupo.save()
                MembroGrupo.objects.create(grupo=grupo, usuario=request.user, representante=True)
            messages.success(request, "Grupo criado dentro da turma.")
            return redirect("plataforma:institutional_program_detail", programa_id=turma.programa_id)
    return render(request, "institutional/group_form.html", {"organizacao": organizacao, "programa": turma.programa, "turma": turma, "form": form, "nav_ativo": "turmas_e_equipes"})


@login_required
@require_http_methods(["GET", "POST"])
def institutional_group_edit(request, group_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None:
        raise Http404
    grupo = get_object_or_404(Grupo, pk=group_id, turma__programa__organizacao=organizacao)
    if not _is_active_group_representative(request, grupo):
        return HttpResponseForbidden("Somente o representante do grupo pode editar seus dados.")
    form = GrupoForm(request.POST or None, instance=grupo)
    if request.method == "POST" and form.is_valid():
        if Grupo.objects.filter(turma=grupo.turma, nome__iexact=form.cleaned_data["nome"]).exclude(pk=grupo.pk).exists():
            form.add_error("nome", "Já existe um grupo com este nome nesta turma.")
        else:
            form.save()
            messages.success(request, "Grupo atualizado.")
            return redirect("plataforma:institutional_group_members", group_id=grupo.pk)
    return render(request, "institutional/structure_form.html", {"organizacao": organizacao, "programa": grupo.turma.programa, "form": form, "titulo": "Editar grupo", "nav_ativo": "turmas_e_equipes"})


@login_required
def institutional_group_members(request, group_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None:
        raise Http404
    grupo = get_object_or_404(Grupo, pk=group_id, turma__programa__organizacao=organizacao)
    if not _can_view_group(request, grupo):
        raise Http404
    pode_gerenciar = _can_invite_to_group(request, grupo)
    eh_membro = MembroGrupo.objects.filter(grupo=grupo, usuario=request.user, status=MembroGrupo.STATUS_ATIVO).exists()
    form = ConviteGrupoForm(request.POST or None)
    if request.method == "POST":
        if not pode_gerenciar:
            return JsonResponse({"detail": "Você não pode convidar pessoas para este grupo."}, status=403)
        if form.is_valid():
            email = form.cleaned_data["email"]
            existing_affiliation = MembroOrganizacao.objects.filter(organizacao=organizacao, usuario__email__iexact=email).first()
            if existing_affiliation and (existing_affiliation.papel != MembroOrganizacao.PAPEL_MEMBRO or existing_affiliation.status != MembroOrganizacao.STATUS_ATIVA):
                form.add_error("email", "A pessoa precisa ser um aluno ativo neste ambiente.")
            elif request.membro_organizacao.papel == MembroOrganizacao.PAPEL_MEMBRO and not (
                existing_affiliation and MembroTurma.objects.filter(turma=grupo.turma, usuario=existing_affiliation.usuario, status=MembroTurma.STATUS_ATIVO).exists()
            ):
                form.add_error("email", "Você pode convidar apenas alunos ativos desta turma.")
            elif MembroGrupo.objects.filter(grupo=grupo, usuario__email__iexact=email, status=MembroGrupo.STATUS_ATIVO).exists():
                form.add_error("email", "Esta pessoa já participa do grupo.")
            elif _usuario_tem_grupo_ativo_na_turma(existing_affiliation.usuario if existing_affiliation else None, grupo.turma, excluir_grupo=grupo):
                form.add_error("email", "Esta pessoa já participa de outro grupo nesta turma.")
            else:
                raw_token = secrets.token_urlsafe(32)
                convite = form.save(commit=False)
                convite.grupo = grupo
                convite.convidado_por = request.user
                convite.hash_token = hashlib.sha256(raw_token.encode()).hexdigest()
                convite.expira_em = timezone.now() + timedelta(days=7)
                convite.save()
                destinatario = User.objects.filter(email__iexact=email).first()
                if destinatario:
                    _notificar(destinatario, "group_invitation", f"Você foi convidado para participar de {grupo.nome}.", request.build_absolute_uri(reverse("plataforma:institutional_group_members", args=[grupo.pk])))
                transaction.on_commit(
                    lambda: deliver_invitation(request, _send_group_invitation_email, convite, raw_token)
                )
                return redirect("plataforma:institutional_group_members", group_id=grupo.pk)
    membros = grupo.membros.select_related("usuario").filter(status=MembroGrupo.STATUS_ATIVO)
    convites = grupo.convites.filter(status=ConviteGrupo.STATUS_PENDENTE, expira_em__gt=timezone.now()).select_related("convidado_por")
    projeto_vinculado = grupo.projetos_institucionais.select_related("projeto", "orientador").first()
    pode_decidir = _can_decide_group(request, grupo)
    solicitacoes = grupo.solicitacoes_entrada.filter(status=SolicitacaoGrupo.STATUS_PENDENTE).select_related("usuario") if pode_decidir else []
    pode_editar = _is_active_group_representative(request, grupo)
    pode_excluir = grupo.criado_por_id == request.user.pk
    return render(request, "institutional/group_members.html", {"organizacao": organizacao, "grupo": grupo, "membros": membros if eh_membro or pode_decidir else [], "convites": convites, "solicitacoes": solicitacoes, "form": form, "pode_gerenciar": pode_gerenciar, "pode_decidir": pode_decidir, "pode_editar": pode_editar, "pode_excluir": pode_excluir, "eh_membro": eh_membro, "projeto_vinculado": projeto_vinculado, "nav_ativo": "turmas_e_equipes"})


@login_required
@require_http_methods(["POST"])
def institutional_group_request_join(request, group_id):
    organizacao = getattr(request, "organizacao", None)
    grupo = get_object_or_404(Grupo, pk=group_id, turma__programa__organizacao=organizacao)
    afiliacao = getattr(request, "membro_organizacao", None)
    if not afiliacao or afiliacao.papel != MembroOrganizacao.PAPEL_MEMBRO or grupo.turma.programa.status != ProgramaInstitucional.STATUS_PUBLICADO or grupo.turma.status != Turma.STATUS_ATIVO:
        return JsonResponse({"detail": "A participação em grupos está disponível para alunos ativos da turma."}, status=403)
    if grupo.status != Grupo.STATUS_ATIVO or not grupo.aberto_para_entrada:
        return JsonResponse({"detail": "Este grupo exige convite."}, status=403)
    if MembroGrupo.objects.filter(grupo=grupo, usuario=request.user, status=MembroGrupo.STATUS_ATIVO).exists():
        return redirect("plataforma:institutional_group_members", group_id=grupo.pk)
    if MembroGrupo.objects.filter(grupo=grupo, usuario=request.user, status=MembroGrupo.STATUS_SUSPENSO).exists():
        return JsonResponse({"detail": "Sua participação neste grupo está suspensa."}, status=403)
    if not MembroTurma.objects.filter(turma=grupo.turma, usuario=request.user, status=MembroTurma.STATUS_ATIVO).exists():
        return JsonResponse({"detail": "Você precisa participar da turma antes de solicitar entrada no grupo."}, status=403)
    if _usuario_tem_grupo_ativo_na_turma(request.user, grupo.turma, excluir_grupo=grupo):
        return JsonResponse({"detail": "Você já participa de outro grupo nesta turma. Saia dele antes de solicitar entrada."}, status=403)
    form = SolicitacaoGrupoForm(request.POST or None)
    if form.is_valid():
        SolicitacaoGrupo.objects.update_or_create(grupo=grupo, usuario=request.user, status=SolicitacaoGrupo.STATUS_PENDENTE, defaults={"mensagem": form.cleaned_data["mensagem"]})
        for membro in grupo.membros.filter(representante=True, status=MembroGrupo.STATUS_ATIVO).select_related("usuario"):
            _notificar(membro.usuario, "group_join_request", f"@{request.user.username} pediu para entrar em {grupo.nome}.", request.build_absolute_uri(reverse("plataforma:institutional_group_members", args=[grupo.pk])))
        messages.success(request, "Sua solicitação para o grupo foi enviada.")
        return redirect("plataforma:institutional_program_detail", programa_id=grupo.turma.programa_id)
    return JsonResponse({"detail": "Solicitação inválida."}, status=400)


@login_required
@require_http_methods(["POST"])
def institutional_group_request_decide(request, request_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None:
        raise Http404
    solicitacao = get_object_or_404(
        SolicitacaoGrupo.objects.select_related("grupo__turma__programa__organizacao"),
        pk=request_id,
        grupo__turma__programa__organizacao=organizacao,
    )
    grupo = solicitacao.grupo
    afiliacao = getattr(request, "membro_organizacao", None)
    pode_decidir = _can_decide_group(request, grupo)
    if afiliacao is None or not pode_decidir:
        return JsonResponse({"detail": "Você não pode decidir solicitações deste grupo."}, status=403)
    if solicitacao.status != SolicitacaoGrupo.STATUS_PENDENTE:
        return JsonResponse({"detail": "Esta solicitação já foi decidida."}, status=400)
    if request.POST.get("acao") not in {"aprovar", "recusar"}:
        return JsonResponse({"detail": "Ação inválida."}, status=400)
    if request.POST.get("acao") == "aprovar":
        if not MembroOrganizacao.objects.filter(organizacao=organizacao, usuario=solicitacao.usuario, papel=MembroOrganizacao.PAPEL_MEMBRO, status=MembroOrganizacao.STATUS_ATIVA).exists() or not MembroTurma.objects.filter(turma=grupo.turma, usuario=solicitacao.usuario, status=MembroTurma.STATUS_ATIVO).exists():
            return JsonResponse({"detail": "O aluno precisa estar ativo nesta turma."}, status=403)
        if MembroGrupo.objects.filter(grupo=grupo, usuario=solicitacao.usuario, status=MembroGrupo.STATUS_SUSPENSO).exists():
            return JsonResponse({"detail": "A participação neste grupo está suspensa."}, status=403)
        if _usuario_tem_grupo_ativo_na_turma(solicitacao.usuario, grupo.turma, excluir_grupo=grupo):
            return JsonResponse({"detail": "Esta pessoa já participa de outro grupo nesta turma."}, status=409)
        MembroGrupo.objects.get_or_create(grupo=grupo, usuario=solicitacao.usuario)
        solicitacao.status = SolicitacaoGrupo.STATUS_APROVADA
    else:
        solicitacao.status = SolicitacaoGrupo.STATUS_RECUSADA
    solicitacao.decidido_por = request.user
    solicitacao.decidido_em = timezone.now()
    solicitacao.save(update_fields=["status", "decidido_por", "decidido_em"])
    _notificar(solicitacao.usuario, "group_request_decision", f"Seu pedido para entrar em {grupo.nome} foi {'aprovado' if solicitacao.status == SolicitacaoGrupo.STATUS_APROVADA else 'recusado'}.", request.build_absolute_uri(reverse("plataforma:institutional_group_members", args=[grupo.pk])))
    return redirect("plataforma:institutional_group_members", group_id=grupo.pk)


@login_required
@require_http_methods(["POST"])
def institutional_group_leave(request, group_id):
    organizacao = getattr(request, "organizacao", None)
    grupo = get_object_or_404(Grupo, pk=group_id, turma__programa__organizacao=organizacao)
    membro = MembroGrupo.objects.filter(grupo=grupo, usuario=request.user, status=MembroGrupo.STATUS_ATIVO).first()
    if not membro:
        return JsonResponse({"detail": "Você não participa deste grupo."}, status=404)
    if membro.representante and grupo.membros.filter(status=MembroGrupo.STATUS_ATIVO).exclude(pk=membro.pk).exists():
        return JsonResponse({"detail": "Transfira a representação para outra pessoa antes de sair."}, status=409)
    membro.status = MembroGrupo.STATUS_SUSPENSO
    membro.save(update_fields=["status"])
    messages.success(request, f"Você saiu de {grupo.nome}.")
    return redirect("plataforma:institutional_program_detail", programa_id=grupo.turma.programa_id)


@login_required
@require_http_methods(["POST"])
def institutional_invite_revoke(request, invite_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None:
        return JsonResponse({"detail": "Você não pode revogar convites neste ambiente."}, status=403)
    convite = get_object_or_404(ConviteGrupo, pk=invite_id, grupo__turma__programa__organizacao=organizacao)
    if not _can_invite_to_group(request, convite.grupo):
        return JsonResponse({"detail": "Você não pode revogar convites neste grupo."}, status=403)
    if ConviteGrupo.objects.filter(pk=convite.pk, status=ConviteGrupo.STATUS_PENDENTE).update(
        status=ConviteGrupo.STATUS_REVOGADO,
    ):
        messages.success(request, "Convite revogado.")
    return redirect("plataforma:institutional_group_members", group_id=convite.grupo_id)


@login_required
@require_http_methods(["POST"])
def institutional_organization_invite_revoke(request, invite_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or not _can_manage_institutional_structure(request):
        return JsonResponse({"detail": "Você não pode revogar convites neste ambiente."}, status=403)
    convite = get_object_or_404(ConviteOrganizacao, pk=invite_id, organizacao=organizacao)
    if ConviteOrganizacao.objects.filter(pk=convite.pk, status=ConviteOrganizacao.STATUS_PENDENTE).update(
        status=ConviteOrganizacao.STATUS_REVOGADO,
    ):
        messages.success(request, "Convite institucional revogado.")
    return redirect("plataforma:institutional_members")


def institutional_invite_accept(request, token):
    return invitation_accept(request, token, "group")


def institutional_organization_invite_accept(request, token):
    return invitation_accept(request, token, "organization")


def _project_scope(request):
    """Retorna apenas projetos do tenant atual ou projetos pessoais globais."""
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None:
        return Project.objects.filter(organizacao__isnull=True)
    return Project.objects.filter(organizacao=organizacao)


def _project_for_request(request, **filters):
    return get_object_or_404(_project_scope(request), **filters)


def _project_accessible(project, user, access_token=""):
    if project.visibility == Project.VISIBILITY_PUBLIC:
        return True
    if user.is_authenticated and project.owner == user:
        return True
    return project.visibility == Project.VISIBILITY_RESTRICTED and str(project.access_token) == str(access_token or "")

def _can_manage_milestones(project, user):
    if not user.is_authenticated:
        return False
    if project.owner == user:
        return True
    return project.memberships.filter(user=user, can_manage_milestones=True).exists()

def _auto_milestone(project, actor, title, description, milestone_type=ProjectMilestone.TYPE_PROGRESS):
    ProjectMilestone.objects.create(project=project, author=actor, title=title, description=description, milestone_type=milestone_type)


def _save_institutional_project_link(project, form, actor):
    if "tipo_projeto" not in form.fields:
        return
    grupo = form.cleaned_data.get("grupo")
    if form.cleaned_data.get("tipo_projeto") == "autonomo":
        VinculoProjetoInstitucional.objects.filter(projeto=project).delete()
        return
    turma = form.cleaned_data["turma"]
    vinculo, _ = VinculoProjetoInstitucional.objects.get_or_create(projeto=project, defaults={"turma": turma, "grupo": grupo, "orientador": form.cleaned_data["orientador"], "vinculado_por": actor})
    if vinculo.turma_id != turma.pk or vinculo.grupo_id != getattr(grupo, "pk", None) or vinculo.orientador_id != form.cleaned_data["orientador"].pk or vinculo.vinculado_por_id != actor.pk:
        vinculo.turma = turma
        vinculo.grupo = grupo
        vinculo.orientador = form.cleaned_data["orientador"]
        vinculo.vinculado_por = actor
        vinculo.save(update_fields=["turma", "grupo", "orientador", "vinculado_por"])


def project_detail(request, pk):
    project = get_object_or_404(_project_scope(request).select_related("owner", "vinculo_institucional__turma__programa__organizacao", "vinculo_institucional__grupo", "vinculo_institucional__orientador"), pk=pk)
    access_token = request.GET.get("access", "")
    if not _project_accessible(project, request.user, access_token):
        raise Http404
    comments = project.comments.filter(parent__isnull=True).select_related("author").prefetch_related("replies__author")
    voted = request.user.is_authenticated and project.votes.filter(user=request.user).exists()
    can_manage = _can_manage_milestones(project, request.user)
    is_project_member = bool(request.user.is_authenticated and project.memberships.filter(user=request.user).exists())
    collaboration_request = project.collaboration_requests.filter(requester=request.user).first() if request.user.is_authenticated else None
    ranking_posicao = None
    if getattr(request, "membro_organizacao", None) and project.organizacao_id == request.organizacao.pk and project.visibility == Project.VISIBILITY_PUBLIC:
        from core.rankings import ranked_projects
        ranked = ranked_projects(Project.objects.filter(organizacao=request.organizacao, votes__isnull=False).distinct(), tenant_id=request.organizacao.pk)
        ranking_posicao = next((index for index, item in enumerate(ranked[:5], 1) if item.pk == project.pk), None)
    return render(request, "projects/detail.html", {"project": project, "is_project_member": is_project_member, "ranking_posicao": ranking_posicao, "organizacao": getattr(request, "organizacao", None), "members": project.memberships.select_related("user"), "links": project.links.all(), "comments": comments, "comment_form": CommentForm(), "milestone_form": MilestoneForm(), "collaboration_form": CollaborationRequestForm(), "vote_count": project.votes.count(), "user_voted": voted, "can_manage": can_manage, "collaboration_request": collaboration_request, "milestones": project.milestones.select_related("author"), "requests": project.collaboration_requests.filter(status=CollaborationRequest.PENDING).select_related("requester") if request.user == project.owner else [], "access_token": access_token, "share_url": request.build_absolute_uri(request.path) + (f"?access={project.access_token}" if project.visibility == Project.VISIBILITY_RESTRICTED else ""), "shareable": project.visibility != Project.VISIBILITY_PRIVATE, "link_formset": ProjectLinkFormSet(instance=project, prefix="links")})
@login_required
def project_create(request):
    organizacao = getattr(request, "organizacao", None)
    form = ProjectBasicsForm(request.POST or None, owner=request.user, organizacao=organizacao)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.organizacao = organizacao
        project.save()
        _save_institutional_project_link(project, form, request.user)
        _auto_milestone(project, request.user, "Projeto iniciado", "O projeto foi criado com título, direção e status.", ProjectMilestone.TYPE_START)
        messages.success(request, "Projeto criado. Você pode adicionar contexto quando quiser.")
        return redirect("plataforma:project_context", pk=project.pk)
    return render(request, "institutional/experience/project_form.html" if getattr(request, "organizacao", None) else "projects/form.html", {"form": form, "heading": "Criar projeto institucional" if organizacao else "Criar projeto", "submit_label": "Continuar", "form_phase": "basics", "organizacao": organizacao})

@login_required
@require_http_methods(["POST"])
def project_delete(request, pk):
    project = _project_for_request(request, pk=pk, owner=request.user)
    title = project.title
    project.delete()
    messages.success(request, f"O projeto {title} foi excluído.")
    return redirect("plataforma:profile", username=request.user.username)

@login_required
def project_context(request, pk):
    project = _project_for_request(request, pk=pk, owner=request.user)
    form = ProjectContextForm(request.POST or None, instance=project)
    formset = ProjectLinkFormSet(request.POST or None, instance=project, prefix="links")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        before = {"category": project.category, "tags": project.tags, "visibility": project.visibility, "seeking_collaborators": project.seeking_collaborators, "links": project.links.count()}
        project = form.save()
        formset.save()
        changes = [label for key, label in [("category", "categoria"), ("tags", "tags"), ("visibility", "visibilidade"), ("seeking_collaborators", "colaboração")] if before[key] != getattr(project, key)]
        if formset.has_changed():
            changes.append("links")
        if changes:
            _auto_milestone(project, request.user, "Contexto atualizado", "Atualizações em: " + ", ".join(changes) + ".")
        if project.visibility == Project.VISIBILITY_PRIVATE:
            messages.info(request, "O projeto continua privado até você decidir compartilhá-lo.")
        else:
            messages.success(request, "Contexto salvo. Seu projeto está pronto para continuar.")
        return redirect("plataforma:project_detail", pk=project.pk)
    return render(request, "institutional/experience/project_form.html" if getattr(request, "organizacao", None) else "projects/form.html", {"form": form, "formset": formset, "heading": "Editar contexto", "submit_label": "Salvar contexto", "form_phase": "context", "project": project, "organizacao": getattr(request, "organizacao", None)})

@login_required
def project_edit(request, pk):
    project = _project_for_request(request, pk=pk, owner=request.user)
    organizacao = getattr(request, "organizacao", None)
    form = ProjectBasicsForm(request.POST or None, instance=project, owner=request.user, organizacao=organizacao)
    if request.method == "POST" and form.is_valid():
        before_title, before_status = project.title, project.status
        project = form.save()
        if organizacao is not None:
            _save_institutional_project_link(project, form, request.user)
        changes = []
        if before_title != project.title: changes.append("nome")
        if before_status != project.status: changes.append("status")
        if changes: _auto_milestone(project, request.user, "Projeto atualizado", "Alterações em: " + ", ".join(changes) + ".")
        messages.success(request, "Projeto atualizado.")
        return redirect("plataforma:project_detail", pk=project.pk)
    return render(request, "institutional/experience/project_form.html" if getattr(request, "organizacao", None) else "projects/form.html", {"form": form, "heading": "Editar projeto institucional" if organizacao else "Editar projeto", "submit_label": "Salvar alterações", "form_phase": "basics", "project": project, "organizacao": organizacao})

@login_required
@require_http_methods(["POST"])
def add_comment(request, pk):
    project = _project_for_request(request, pk=pk)
    if not _project_accessible(project, request.user, request.POST.get("access") or request.GET.get("access")):
        raise Http404
    if project.owner_id == request.user.pk:
        return HttpResponseForbidden("O autor não pode comentar no próprio projeto.")
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.project, comment.author = project, request.user
        parent_id = request.POST.get("parent")
        if parent_id:
            parent = get_object_or_404(ProjectComment, pk=parent_id, project=project)
            if parent.parent_id:
                messages.error(request, "As respostas têm apenas um nível neste MVP.")
                access = request.POST.get("access", "")
                return redirect(f"/projetos/{pk}/?access={access}" if access else f"/projetos/{pk}/")
            comment.parent = parent
        comment.save()
    access = request.POST.get("access", "")
    return redirect(f"/projetos/{pk}/?access={access}" if access else f"/projetos/{pk}/")


@login_required
@require_http_methods(["POST"])
def edit_comment(request, comment_id):
    comment = get_object_or_404(
        ProjectComment,
        pk=comment_id,
        author=request.user,
        project__in=_project_scope(request),
    )
    if comment.project.owner_id == request.user.pk:
        return HttpResponseForbidden("O autor não pode comentar no próprio projeto.")
    form = CommentForm(request.POST, instance=comment)
    if form.is_valid():
        form.save()
    return redirect("plataforma:project_detail", pk=comment.project_id)


@login_required
@require_http_methods(["POST"])
def delete_comment(request, comment_id):
    comment = get_object_or_404(
        ProjectComment,
        pk=comment_id,
        author=request.user,
        project__in=_project_scope(request),
    )
    project_id = comment.project_id
    comment.delete()
    return redirect("plataforma:project_detail", pk=project_id)


@login_required
@require_http_methods(["POST"])
def toggle_vote(request, pk):
    project = _project_for_request(request, pk=pk)
    if not _project_accessible(project, request.user, request.POST.get("access") or request.GET.get("access")):
        raise Http404
    if project.owner_id == request.user.pk:
        return HttpResponseForbidden("O autor não pode reconhecer o próprio projeto.")
    vote, created = ProjectVote.objects.get_or_create(project=project, user=request.user)
    if not created:
        vote.delete()
    next_url = _safe_local_next(request, request.POST.get("next", ""))
    if next_url:
        return redirect(next_url)
    access = request.POST.get("access", "")
    return redirect(f"/projetos/{pk}/?access={access}" if access else f"/projetos/{pk}/")


@login_required
@require_http_methods(["POST"])
def set_milestone_permission(request, pk):
    project = _project_for_request(request, pk=pk, owner=request.user)
    member = get_object_or_404(ProjectMember, pk=request.POST.get("member_id"), project=project)
    member.can_manage_milestones = request.POST.get("can_manage") == "1"
    member.save(update_fields=["can_manage_milestones"])
    messages.success(request, "Permissão de marcos atualizada.")
    return redirect("plataforma:project_detail", pk=pk)

@login_required
@require_http_methods(["POST"])
def add_milestone(request, pk):
    project = _project_for_request(request, pk=pk)
    if not _can_manage_milestones(project, request.user):
        raise Http404
    form = MilestoneForm(request.POST)
    if form.is_valid():
        milestone = form.save(commit=False)
        milestone.project, milestone.author = project, request.user
        milestone.save()
    return redirect("plataforma:project_detail", pk=pk)


@login_required
@require_http_methods(["POST"])
def edit_milestone(request, milestone_id):
    milestone = get_object_or_404(
        ProjectMilestone,
        pk=milestone_id,
        author=request.user,
        project__in=_project_scope(request),
    )
    form = MilestoneForm(request.POST, instance=milestone)
    if form.is_valid():
        form.save()
    return redirect("plataforma:project_detail", pk=milestone.project_id)


@login_required
@require_http_methods(["POST"])
def delete_milestone(request, milestone_id):
    milestone = get_object_or_404(
        ProjectMilestone,
        pk=milestone_id,
        author=request.user,
        project__in=_project_scope(request),
    )
    project_id = milestone.project_id
    milestone.delete()
    return redirect("plataforma:project_detail", pk=project_id)


@login_required
@require_http_methods(["POST"])
def request_collaboration(request, pk):
    project = _project_for_request(request, pk=pk, visibility=Project.VISIBILITY_PUBLIC)
    if project.owner == request.user or project.memberships.filter(user=request.user).exists():
        return redirect("plataforma:project_detail", pk=pk)
    form = CollaborationRequestForm(request.POST)
    if form.is_valid():
        collaboration, created = CollaborationRequest.objects.get_or_create(project=project, requester=request.user, defaults={"message": form.cleaned_data["message"]})
        if created:
            Notification.objects.create(recipient=project.owner, kind="collaboration_request", message=f"{request.user.get_username()} quer colaborar em {project.title}.", url=project_notification_url(request, project))
    return redirect("plataforma:project_detail", pk=pk)


@login_required
@require_http_methods(["POST"])
def decide_collaboration(request, request_id):
    collaboration = get_object_or_404(
        CollaborationRequest.objects.select_related("project", "requester"),
        pk=request_id,
        project__in=_project_scope(request).filter(owner=request.user),
        status=CollaborationRequest.PENDING,
    )
    decision = request.POST.get("decision")
    if decision not in (CollaborationRequest.ACCEPTED, CollaborationRequest.REJECTED):
        return redirect("plataforma:project_detail", pk=collaboration.project_id)
    project_title, requester = collaboration.project.title, collaboration.requester
    status_label = "aceito" if decision == CollaborationRequest.ACCEPTED else "recusado"
    if decision == CollaborationRequest.ACCEPTED:
        if collaboration.project.organizacao_id and not MembroOrganizacao.objects.filter(
            organizacao_id=collaboration.project.organizacao_id, usuario=requester,
            status=MembroOrganizacao.STATUS_ATIVA,
        ).exists():
            return JsonResponse({"detail": "O solicitante não possui afiliação ativa neste ambiente."}, status=403)
        ProjectMember.objects.get_or_create(project=collaboration.project, user=collaboration.requester, defaults={"role": "Colaborador"})
    Notification.objects.create(recipient=requester, kind="collaboration_decision", message=f"Seu pedido para {project_title} foi {status_label}.", url=project_notification_url(request, collaboration.project))
    collaboration.delete()
    return redirect("plataforma:project_detail", pk=collaboration.project_id)


@login_required
def inbox(request):
    if getattr(request, "organizacao", None):
        from .experience import inbox as institutional_inbox
        return institutional_inbox(request)
    notifications = request.user.notifications.all()
    request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
    return render(request, "notifications/inbox.html", {"notifications": notifications})


def saude(request):
    return JsonResponse({"status": "ok", "deployment": deployment_metadata()})


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
    if urlparse(settings.STATUS_API_URL).scheme not in {"http", "https"}:
        return None
    request = Request(
        settings.STATUS_API_URL,
        headers={"Accept": "application/json", "User-Agent": "PalacioMentalStatus/1.0"},
    )
    with urlopen(request, timeout=settings.STATUS_API_TIMEOUT) as response:  # nosec B310: esquema validado acima
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


def _deployment_metrics(deployment):
    labels = {
        "commit": "Commit",
        "author": "Autor",
        "branch": "Branch",
        "service": "Serviço",
        "environment": "Ambiente",
    }
    return [
        {"label": labels[key], "value": value[:12] if key == "commit" else value}
        for key, value in deployment.items()
        if key in labels and value
    ]


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
        deployment = payload.get("deployment") or django.get("deployment") or {}
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
                    "Aplicação web (Django)",
                    "⌂",
                    django.get("status"),
                    _response_metric(django) + ([{"label": "Verificação", "value": "GET /pronto"}] if django else []),
                    "Servidor web",
                ),
                _service_card(
                    "API de status", "↗", payload.get("status"), _response_metric(payload), "APIs e serviços"
                ),
            ],
            deployment_metrics=_deployment_metrics(deployment),
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
