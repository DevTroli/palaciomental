"""Entrada pública controlada por convite, sem abrir o conteúdo do tenant."""

import hashlib
from urllib.parse import urlencode

from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .forms import MemberCreationForm
from .models import (
    ConviteGrupo, ConviteOrganizacao, MemberProfile, MembroGrupo,
    MembroOrganizacao, MembroTurma,
)


class InvitationRegistrationForm(MemberCreationForm):
    def __init__(self, *args, invited_email, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = invited_email
        self.fields["email"].disabled = True
        self.fields["email"].help_text = "Este convite é exclusivo deste endereço."
        self.fields["first_name"].required = False
        self.fields["username"].help_text = "Será usado para entrar e identificar seu perfil."
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["username"].widget.attrs.pop("autofocus", None)
        self.fields["password2"].help_text = ""


def _organization(invitation, kind):
    if kind == "group":
        return invitation.grupo.turma.programa.organizacao
    return invitation.organizacao


def _invitation(request, token, kind, *, locked=False):
    model = ConviteGrupo if kind == "group" else ConviteOrganizacao
    relation = "grupo__turma__programa__organizacao" if kind == "group" else "organizacao"
    queryset = model.objects.select_related(relation)
    if locked:
        queryset = queryset.select_for_update(of=("self",))
    invitation = get_object_or_404(
        queryset, hash_token=hashlib.sha256(token.encode()).hexdigest(),
    )
    organization = _organization(invitation, kind)
    if getattr(request, "organizacao", None) != organization:
        raise Http404
    if invitation.status != model.STATUS_PENDENTE or invitation.expira_em <= timezone.now():
        raise PermissionDenied("Este convite não está mais disponível.")
    return invitation


def invitation_login_target(request, path, user):
    """Autoriza só o retorno a um convite válido, nunca o acesso geral ao tenant."""
    try:
        match = resolve(path)
        kinds = {
            "plataforma:institutional_invite_accept": "group",
            "plataforma:institutional_organization_invite_accept": "organization",
        }
        kind = kinds.get(match.view_name)
        if kind is None:
            return False
        invitation = _invitation(request, match.kwargs["token"], kind)
    except (Resolver404, Http404, PermissionDenied):
        return False
    return invitation.email.casefold() == user.email.casefold()


def _accept(invitation, user, kind):
    if invitation.email.casefold() != user.email.casefold():
        raise PermissionDenied("Este convite foi emitido para outro endereço de e-mail.")
    organization = _organization(invitation, kind)
    affiliation, created = MembroOrganizacao.objects.get_or_create(
        organizacao=organization,
        usuario=user,
        defaults={"papel": "membro" if kind == "group" else invitation.papel},
    )
    if kind == "organization":
        if not created and affiliation.status != MembroOrganizacao.STATUS_ATIVA:
            affiliation.status = MembroOrganizacao.STATUS_ATIVA
            affiliation.papel = invitation.papel
            affiliation.save(update_fields=["status", "papel"])
        elif not created and affiliation.papel != invitation.papel:
            raise PermissionDenied("Sua conta já possui outro papel neste ambiente.")
    else:
        if affiliation.status != MembroOrganizacao.STATUS_ATIVA:
            raise PermissionDenied("Sua afiliação está suspensa. Procure a gestão.")
        class_member, _ = MembroTurma.objects.get_or_create(
            turma=invitation.grupo.turma, usuario=user,
        )
        if class_member.status != MembroTurma.STATUS_ATIVO:
            raise PermissionDenied("Sua participação na turma está suspensa. Procure a gestão.")
        member, _ = MembroGrupo.objects.get_or_create(grupo=invitation.grupo, usuario=user)
        if member.status != MembroGrupo.STATUS_ATIVO:
            member.status = MembroGrupo.STATUS_ATIVO
            member.save(update_fields=["status"])
    invitation.status = invitation.STATUS_ACEITO
    invitation.aceito_em = timezone.now()
    invitation.save(update_fields=["status", "aceito_em"])


@never_cache
@sensitive_post_parameters("password1", "password2")
@require_http_methods(["GET", "POST"])
def invitation_accept(request, token, kind):
    invitation = _invitation(request, token, kind)
    if request.user.is_authenticated and request.user.email.casefold() != invitation.email.casefold():
        raise PermissionDenied("Este convite foi emitido para outro endereço de e-mail.")

    form = InvitationRegistrationForm(invited_email=invitation.email)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "register" and not request.user.is_authenticated:
            with transaction.atomic():
                invitation = _invitation(request, token, kind, locked=True)
                form = InvitationRegistrationForm(request.POST, invited_email=invitation.email)
                if form.is_valid():
                    user = form.save()
                    MemberProfile.objects.create(user=user)
                    login(request, user)
                    return redirect(request.path)
        elif action == "accept" and request.user.is_authenticated:
            with transaction.atomic():
                invitation = _invitation(request, token, kind, locked=True)
                _accept(invitation, request.user, kind)
            if kind == "group":
                return redirect(
                    "plataforma:institutional_program_detail",
                    programa_id=invitation.grupo.turma.programa_id,
                )
            return redirect("plataforma:projects")
        else:
            return HttpResponseBadRequest("Ação de convite inválida.")

    response = render(request, "auth/invitation.html", {
        "convite": invitation,
        "grupo": invitation.grupo if kind == "group" else None,
        "form": form,
        "login_url": reverse("plataforma:login") + "?" + urlencode({"next": request.path}),
    })
    # Mantém somente a origem: não vaza o token e permite o fallback Referer
    # do CSRF em HTTPS quando o navegador não enviar Origin.
    response["Referrer-Policy"] = "strict-origin"
    return response
