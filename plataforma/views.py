import json
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.templatetags.static import static
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .forms import CollaborationRequestForm, CommentForm, ConviteOrganizacaoForm, ConviteTurmaGrupoForm, MemberCreationForm, MilestoneForm, ProfileForm, ProgramaInstitucionalForm, ProjectBasicsForm, ProjectContextForm, ProjectForm, ProjectLinkFormSet, TurmaGrupoForm
from .models import CollaborationRequest, ConviteOrganizacao, ConviteTurmaGrupo, MemberProfile, MembroOrganizacao, MembroTurmaGrupo, Notification, ProgramaInstitucional, Project, ProjectComment, ProjectLink, ProjectMember, ProjectMilestone, ProjectVote, ProjetoTurmaGrupo, TurmaGrupo
from .services import emitir_convite_organizacao, papeis_convidaveis

def register(request):
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


def login_view(request):
    from django.contrib.auth.forms import AuthenticationForm
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next") or "plataforma:projects")
    return render(request, "auth/login.html", {"form": form})


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect("core:index")


def profile(request, username):
    user = get_object_or_404(User, username=username)
    MemberProfile.objects.get_or_create(user=user)
    project_scope = _project_scope(request)
    owned = project_scope.filter(owner=user)
    if request.user != user:
        owned = owned.filter(visibility=Project.VISIBILITY_PUBLIC)
    collaborated = project_scope.filter(memberships__user=user, visibility=Project.VISIBILITY_PUBLIC).exclude(owner=user).distinct()
    return render(request, "members/profile.html", {"member": user, "owned_projects": owned, "collaborated_projects": collaborated})


@login_required
def profile_edit(request):
    profile_obj, _ = MemberProfile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile_obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Seu perfil foi atualizado.")
        return redirect("plataforma:profile", username=request.user.username)
    return render(request, "members/profile_edit.html", {"form": form})


def projects(request):
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
        queryset = queryset.order_by("-relevance", "-updated_at")
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
    return render(
        request,
        "institutional/management.html",
        {"organizacao": organizacao, "afiliacao": afiliacao, "identidade": getattr(organizacao, "identidade", None)},
    )


@login_required
def institutional_members(request):
    organizacao = getattr(request, "organizacao", None)
    afiliacao = getattr(request, "membro_organizacao", None)
    if organizacao is None or afiliacao is None or not _can_manage_affiliations(request):
        return JsonResponse({"detail": "Você não pode administrar afiliações neste ambiente."}, status=403)
    papeis = papeis_convidaveis(afiliacao.papel)
    if request.method == "POST" and request.POST.get("acao") == "convidar":
        form = ConviteOrganizacaoForm(request.POST, papeis_permitidos=papeis)
        if form.is_valid():
            try:
                convite, raw_token = emitir_convite_organizacao(
                    organizacao, afiliacao, form.cleaned_data["email"], form.cleaned_data["papel"]
                )
            except ValidationError as exc:
                form.add_error(None, exc.message)
            else:
                transaction.on_commit(lambda: _send_organization_invitation_email(request, convite, raw_token))
                messages.success(request, f"Convite criado para {convite.email}.")
                return redirect("plataforma:institutional_members")
    elif request.method == "POST":
        membro = get_object_or_404(MembroOrganizacao, pk=request.POST.get("membro_id"), organizacao=organizacao)
        acao = request.POST.get("acao")
        if membro.papel == MembroOrganizacao.PAPEL_PROPRIETARIO and request.user != membro.usuario:
            return JsonResponse({"detail": "Apenas o proprietário pode alterar outro proprietário."}, status=403)
        if acao in {"suspender", "remover"}:
            if membro.usuario_id == request.user.pk:
                return JsonResponse({"detail": "Você não pode remover ou suspender sua própria afiliação."}, status=400)
            if membro.papel == MembroOrganizacao.PAPEL_PROPRIETARIO and organizacao.afiliacoes.filter(papel=MembroOrganizacao.PAPEL_PROPRIETARIO, status=MembroOrganizacao.STATUS_ATIVA).count() <= 1:
                return JsonResponse({"detail": "A organização precisa manter pelo menos um proprietário ativo."}, status=400)
            membro.status = MembroOrganizacao.STATUS_SUSPENSA
            membro.save(update_fields=["status"])
            messages.success(request, "Afiliação suspensa.")
        elif acao == "ativar":
            membro.status = MembroOrganizacao.STATUS_ATIVA
            membro.save(update_fields=["status"])
            messages.success(request, "Afiliação reativada.")
        elif acao == "papel":
            novo_papel = request.POST.get("papel")
            if novo_papel not in dict(MembroOrganizacao.PAPEL_CHOICES):
                return JsonResponse({"detail": "Papel institucional inválido."}, status=400)
            if novo_papel == MembroOrganizacao.PAPEL_PROPRIETARIO and request.membro_organizacao.papel != MembroOrganizacao.PAPEL_PROPRIETARIO:
                return JsonResponse({"detail": "Somente o proprietário pode conceder o papel de proprietário."}, status=403)
            if membro.papel == MembroOrganizacao.PAPEL_PROPRIETARIO and novo_papel != MembroOrganizacao.PAPEL_PROPRIETARIO and organizacao.afiliacoes.filter(papel=MembroOrganizacao.PAPEL_PROPRIETARIO, status=MembroOrganizacao.STATUS_ATIVA).count() <= 1:
                return JsonResponse({"detail": "A organização precisa manter pelo menos um proprietário ativo."}, status=400)
            membro.papel = novo_papel
            membro.save(update_fields=["papel"])
            messages.success(request, "Papel institucional atualizado.")
        return redirect("plataforma:institutional_members")
    membros = organizacao.afiliacoes.select_related("usuario").order_by("papel", "usuario__username")
    convite_form = locals().get("form") if request.method == "POST" and request.POST.get("acao") == "convidar" else ConviteOrganizacaoForm(papeis_permitidos=papeis)
    convites = organizacao.convites.filter(status=ConviteOrganizacao.STATUS_PENDENTE, expira_em__gt=timezone.now()).select_related("convidado_por").order_by("expira_em")
    return render(request, "institutional/members.html", {"organizacao": organizacao, "identidade": getattr(organizacao, "identidade", None), "membros": membros, "papeis": MembroOrganizacao.PAPEL_CHOICES, "convite_form": convite_form, "convites": convites, "papeis_convidaveis": papeis})


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
    }
    email = EmailMultiAlternatives(
        subject=f"Convite para entrar em {convite.organizacao.nome}",
        body=render_to_string("emails/organization_invitation.txt", contexto),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[convite.email],
    )
    email.attach_alternative(render_to_string("emails/organization_invitation.html", contexto), "text/html")
    email.send(fail_silently=False)


def _can_invite_to_group(request, group):
    afiliacao = getattr(request, "membro_organizacao", None)
    if afiliacao is None:
        return False
    if afiliacao.papel in {MembroOrganizacao.PAPEL_PROPRIETARIO, MembroOrganizacao.PAPEL_GESTOR}:
        return True
    if afiliacao.papel != MembroOrganizacao.PAPEL_PROFESSOR:
        return False
    return group.professor_responsavel_id == request.user.pk or group.membros.filter(
        usuario=request.user,
        papel=MembroTurmaGrupo.PAPEL_PROFESSOR,
        status=MembroTurmaGrupo.STATUS_ATIVO,
    ).exists()


def _can_view_group(request, group):
    afiliacao = getattr(request, "membro_organizacao", None)
    if afiliacao is None:
        return False
    if afiliacao.papel in {MembroOrganizacao.PAPEL_PROPRIETARIO, MembroOrganizacao.PAPEL_GESTOR}:
        return True
    if group.professor_responsavel_id == request.user.pk:
        return True
    return group.membros.filter(usuario=request.user, status=MembroTurmaGrupo.STATUS_ATIVO).exists()


def _send_group_invitation_email(request, convite, raw_token):
    invite_url = request.build_absolute_uri(reverse("plataforma:institutional_invite_accept", kwargs={"token": raw_token}))
    grupo = convite.turma_grupo
    contexto = {
        "convite": convite,
        "grupo": grupo,
        "programa": grupo.programa,
        "organizacao": grupo.programa.organizacao,
        "identidade": getattr(grupo.programa.organizacao, "identidade", None),
        "convidado_por": convite.convidado_por,
        "invite_url": invite_url,
    }
    email = EmailMultiAlternatives(
        subject=f"Convite para participar de {grupo.nome}",
        body=render_to_string("emails/institutional_invitation.txt", contexto),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[convite.email],
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
                messages.success(request, "Programa criado. Agora você pode adicionar uma turma ou grupo.")
                return redirect("plataforma:institutional_program_detail", programa_id=programa.pk)
    programas = ProgramaInstitucional.objects.filter(organizacao=organizacao).prefetch_related("turmas_grupos")
    return render(
        request,
        "institutional/programs.html",
        {"organizacao": organizacao, "programas": programas, "form": form, "pode_gerenciar": _can_manage_institutional_structure(request)},
    )


@login_required
def institutional_program_detail(request, programa_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None:
        raise Http404
    programa = get_object_or_404(ProgramaInstitucional, pk=programa_id, organizacao=organizacao)
    return render(
        request,
        "institutional/program_detail.html",
        {"organizacao": organizacao, "programa": programa, "pode_gerenciar": _can_manage_institutional_structure(request)},
    )


@login_required
def institutional_group_create(request, programa_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or not _can_manage_institutional_structure(request):
        return JsonResponse({"detail": "Você não pode criar uma turma ou grupo neste ambiente."}, status=403)
    programa = get_object_or_404(ProgramaInstitucional, pk=programa_id, organizacao=organizacao)
    form = TurmaGrupoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        turma_grupo = form.save(commit=False)
        turma_grupo.programa = programa
        turma_grupo.criado_por = request.user
        turma_grupo.save()
        messages.success(request, "Turma ou grupo criado.")
        return redirect("plataforma:institutional_program_detail", programa_id=programa.pk)
    return render(request, "institutional/group_form.html", {"organizacao": organizacao, "programa": programa, "form": form})


@login_required
def institutional_group_members(request, group_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None:
        raise Http404
    grupo = get_object_or_404(TurmaGrupo, pk=group_id, programa__organizacao=organizacao)
    if not _can_view_group(request, grupo):
        raise Http404
    pode_gerenciar = _can_invite_to_group(request, grupo)
    form = ConviteTurmaGrupoForm(request.POST or None)
    if request.method == "POST":
        if not pode_gerenciar:
            return JsonResponse({"detail": "Você não pode convidar pessoas para este grupo."}, status=403)
        if form.is_valid():
            email = form.cleaned_data["email"]
            if MembroTurmaGrupo.objects.filter(turma_grupo=grupo, usuario__email__iexact=email, status=MembroTurmaGrupo.STATUS_ATIVO).exists():
                form.add_error("email", "Esta pessoa já participa do grupo.")
            else:
                raw_token = secrets.token_urlsafe(32)
                convite = form.save(commit=False)
                convite.turma_grupo = grupo
                convite.convidado_por = request.user
                convite.hash_token = hashlib.sha256(raw_token.encode()).hexdigest()
                convite.expira_em = timezone.now() + timedelta(days=7)
                convite.save()
                link = request.build_absolute_uri(reverse("plataforma:institutional_invite_accept", kwargs={"token": raw_token}))
                transaction.on_commit(lambda: _send_group_invitation_email(request, convite, raw_token))
                messages.success(request, f"Convite criado para {email}. Link para envio: {link}")
                return redirect("plataforma:institutional_group_members", group_id=grupo.pk)
    membros = grupo.membros.select_related("usuario").filter(status=MembroTurmaGrupo.STATUS_ATIVO)
    convites = grupo.convites.filter(status=ConviteTurmaGrupo.STATUS_PENDENTE, expira_em__gt=timezone.now()).select_related("convidado_por")
    return render(request, "institutional/group_members.html", {"organizacao": organizacao, "grupo": grupo, "membros": membros, "convites": convites, "form": form, "pode_gerenciar": pode_gerenciar})


@login_required
@require_http_methods(["POST"])
def institutional_invite_revoke(request, invite_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or not _can_manage_institutional_structure(request):
        return JsonResponse({"detail": "Você não pode revogar convites neste ambiente."}, status=403)
    convite = get_object_or_404(ConviteTurmaGrupo, pk=invite_id, turma_grupo__programa__organizacao=organizacao)
    if convite.status == ConviteTurmaGrupo.STATUS_PENDENTE:
        convite.status = ConviteTurmaGrupo.STATUS_REVOGADO
        convite.save(update_fields=["status"])
        messages.success(request, "Convite revogado.")
    return redirect("plataforma:institutional_group_members", group_id=convite.turma_grupo_id)


@login_required
@require_http_methods(["POST"])
def institutional_organization_invite_revoke(request, invite_id):
    organizacao = getattr(request, "organizacao", None)
    if organizacao is None or not _can_manage_institutional_structure(request):
        return JsonResponse({"detail": "Você não pode revogar convites neste ambiente."}, status=403)
    convite = get_object_or_404(ConviteOrganizacao, pk=invite_id, organizacao=organizacao)
    if convite.status == ConviteOrganizacao.STATUS_PENDENTE:
        convite.status = ConviteOrganizacao.STATUS_REVOGADO
        convite.save(update_fields=["status"])
        messages.success(request, "Convite institucional revogado.")
    return redirect("plataforma:institutional_members")


def institutional_invite_accept(request, token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    convite = get_object_or_404(ConviteTurmaGrupo.objects.select_related("turma_grupo__programa__organizacao"), hash_token=digest)
    if convite.status != ConviteTurmaGrupo.STATUS_PENDENTE or convite.expira_em <= timezone.now():
        return HttpResponseForbidden("Este convite não está mais disponível.")
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
    if request.user.email.lower() != convite.email.lower():
        return HttpResponseForbidden("Este convite foi emitido para outro endereço de e-mail.")
    organizacao = convite.turma_grupo.programa.organizacao
    with transaction.atomic():
        MembroOrganizacao.objects.get_or_create(
            organizacao=organizacao,
            usuario=request.user,
            defaults={"papel": MembroOrganizacao.PAPEL_MEMBRO},
        )
        membro, _ = MembroTurmaGrupo.objects.get_or_create(turma_grupo=convite.turma_grupo, usuario=request.user, defaults={"papel": convite.papel})
        if membro.status != MembroTurmaGrupo.STATUS_ATIVO:
            membro.status = MembroTurmaGrupo.STATUS_ATIVO
            membro.papel = convite.papel
            membro.save(update_fields=["status", "papel"])
        convite.status = ConviteTurmaGrupo.STATUS_ACEITO
        convite.aceito_em = timezone.now()
        convite.save(update_fields=["status", "aceito_em"])
    return redirect("plataforma:institutional_program_detail", programa_id=convite.turma_grupo.programa_id)


def institutional_organization_invite_accept(request, token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    convite = get_object_or_404(ConviteOrganizacao.objects.select_related("organizacao"), hash_token=digest)
    if convite.status != ConviteOrganizacao.STATUS_PENDENTE or convite.expira_em <= timezone.now():
        return HttpResponseForbidden("Este convite não está mais disponível.")
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
    if request.user.email.lower() != convite.email.lower():
        return HttpResponseForbidden("Este convite foi emitido para outro endereço de e-mail.")
    with transaction.atomic():
        afiliacao, criada = MembroOrganizacao.objects.get_or_create(
            organizacao=convite.organizacao,
            usuario=request.user,
            defaults={"papel": convite.papel},
        )
        if not criada:
            if afiliacao.status != MembroOrganizacao.STATUS_ATIVA:
                afiliacao.status = MembroOrganizacao.STATUS_ATIVA
                afiliacao.papel = convite.papel
                afiliacao.save(update_fields=["status", "papel"])
            elif afiliacao.papel != convite.papel:
                return HttpResponseForbidden("Sua conta já possui outro papel neste ambiente.")
        convite.status = ConviteOrganizacao.STATUS_ACEITO
        convite.aceito_em = timezone.now()
        convite.save(update_fields=["status", "aceito_em"])
    return redirect("plataforma:projects")


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

def project_detail(request, pk):
    project = get_object_or_404(_project_scope(request).select_related("owner"), pk=pk)
    access_token = request.GET.get("access", "")
    if not _project_accessible(project, request.user, access_token):
        raise Http404
    comments = project.comments.filter(parent__isnull=True).select_related("author").prefetch_related("replies__author")
    voted = request.user.is_authenticated and project.votes.filter(user=request.user).exists()
    can_manage = _can_manage_milestones(project, request.user)
    collaboration_request = project.collaboration_requests.filter(requester=request.user).first() if request.user.is_authenticated else None
    return render(request, "projects/detail.html", {"project": project, "organizacao": getattr(request, "organizacao", None), "members": project.memberships.select_related("user"), "links": project.links.all(), "comments": comments, "comment_form": CommentForm(), "milestone_form": MilestoneForm(), "collaboration_form": CollaborationRequestForm(), "vote_count": project.votes.count(), "user_voted": voted, "can_manage": can_manage, "collaboration_request": collaboration_request, "milestones": project.milestones.select_related("author"), "requests": project.collaboration_requests.filter(status=CollaborationRequest.PENDING).select_related("requester") if request.user == project.owner else [], "access_token": access_token, "share_url": request.build_absolute_uri(request.path) + (f"?access={project.access_token}" if project.visibility == Project.VISIBILITY_RESTRICTED else ""), "shareable": project.visibility != Project.VISIBILITY_PRIVATE, "link_formset": ProjectLinkFormSet(instance=project, prefix="links")})
@login_required
def project_create(request):
    organizacao = getattr(request, "organizacao", None)
    form = ProjectBasicsForm(request.POST or None, owner=request.user, organizacao=organizacao)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.organizacao = organizacao
        project.save()
        turma_grupo = form.cleaned_data.get("turma_grupo")
        if turma_grupo is not None:
            ProjetoTurmaGrupo.objects.create(projeto=project, turma_grupo=turma_grupo, vinculado_por=request.user)
        _auto_milestone(project, request.user, "Projeto iniciado", "O projeto foi criado com título, direção e status.", ProjectMilestone.TYPE_START)
        messages.success(request, "Projeto criado. Você pode adicionar contexto quando quiser.")
        return redirect("plataforma:project_context", pk=project.pk)
    return render(request, "projects/form.html", {"form": form, "heading": "Criar projeto institucional" if organizacao else "Criar projeto", "submit_label": "Continuar", "form_phase": "basics", "organizacao": organizacao})

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
    return render(request, "projects/form.html", {"form": form, "formset": formset, "heading": "Editar contexto", "submit_label": "Salvar contexto", "form_phase": "context", "project": project, "organizacao": getattr(request, "organizacao", None)})

@login_required
def project_edit(request, pk):
    project = _project_for_request(request, pk=pk, owner=request.user)
    organizacao = getattr(request, "organizacao", None)
    form = ProjectBasicsForm(request.POST or None, instance=project, organizacao=organizacao)
    if request.method == "POST" and form.is_valid():
        before_title, before_status = project.title, project.status
        project = form.save()
        if organizacao is not None:
            turma_grupo = form.cleaned_data.get("turma_grupo")
            vinculo, _ = ProjetoTurmaGrupo.objects.get_or_create(projeto=project, defaults={"turma_grupo": turma_grupo, "vinculado_por": request.user}) if turma_grupo else (None, False)
            if turma_grupo is not None:
                if vinculo.turma_grupo_id != turma_grupo.pk or vinculo.vinculado_por_id != request.user.pk:
                    vinculo.turma_grupo = turma_grupo
                    vinculo.vinculado_por = request.user
                    vinculo.save(update_fields=["turma_grupo", "vinculado_por"])
            else:
                ProjetoTurmaGrupo.objects.filter(projeto=project).delete()
        changes = []
        if before_title != project.title: changes.append("nome")
        if before_status != project.status: changes.append("status")
        if changes: _auto_milestone(project, request.user, "Projeto atualizado", "Alterações em: " + ", ".join(changes) + ".")
        messages.success(request, "Projeto atualizado.")
        return redirect("plataforma:project_detail", pk=project.pk)
    return render(request, "projects/form.html", {"form": form, "heading": "Editar projeto institucional" if organizacao else "Editar projeto", "submit_label": "Salvar alterações", "form_phase": "basics", "project": project, "organizacao": organizacao})

@login_required
@require_http_methods(["POST"])
def add_comment(request, pk):
    project = _project_for_request(request, pk=pk)
    if not _project_accessible(project, request.user, request.POST.get("access") or request.GET.get("access")):
        raise Http404
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
    vote, created = ProjectVote.objects.get_or_create(project=project, user=request.user)
    if not created:
        vote.delete()
    if request.POST.get("next"):
        return redirect(request.POST["next"])
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
            Notification.objects.create(recipient=project.owner, kind="collaboration_request", message=f"{request.user.get_username()} quer colaborar em {project.title}.", url=f"/projetos/{project.pk}/")
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
    project_title, project_pk, requester = collaboration.project.title, collaboration.project.pk, collaboration.requester
    status_label = "aceito" if decision == CollaborationRequest.ACCEPTED else "recusado"
    if decision == CollaborationRequest.ACCEPTED:
        ProjectMember.objects.get_or_create(project=collaboration.project, user=collaboration.requester, defaults={"role": "Colaborador"})
    Notification.objects.create(recipient=requester, kind="collaboration_decision", message=f"Seu pedido para {project_title} foi {status_label}.", url=f"/projetos/{project_pk}/")
    collaboration.delete()
    return redirect("plataforma:project_detail", pk=collaboration.project_id)


@login_required
def inbox(request):
    notifications = request.user.notifications.all()
    request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
    return render(request, "notifications/inbox.html", {"notifications": notifications})


def saude(request):
    deployment = {
        label: value
        for label, value in {
            "commit": os.getenv("RAILWAY_GIT_COMMIT_SHA"),
            "author": os.getenv("RAILWAY_GIT_AUTHOR"),
            "branch": os.getenv("RAILWAY_GIT_BRANCH"),
            "service": os.getenv("RAILWAY_SERVICE_NAME"),
            "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME"),
        }.items()
        if value
    }
    return JsonResponse({"status": "ok", "deployment": deployment})


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
    request = Request(
        settings.STATUS_API_URL,
        headers={"Accept": "application/json", "User-Agent": "PalacioMentalStatus/1.0"},
    )
    with urlopen(request, timeout=settings.STATUS_API_TIMEOUT) as response:
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
                    _response_metric(django) + ([{"label": "Verificação", "value": "GET /saude"}] if django else []),
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
