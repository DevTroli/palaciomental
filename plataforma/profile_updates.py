"""Persistência do perfil sem remover mídia ainda referenciada."""
import logging
from pathlib import PurePosixPath
from uuid import uuid4

from django.db import transaction

from .models import MemberProfile

logger = logging.getLogger(__name__)


def remove_unused_avatar(storage, name):
    if not name:
        return
    try:
        if not MemberProfile.objects.filter(avatar=name).exists():
            storage.delete(name)
        return True
    except Exception:
        # Não registrar mensagens do provedor, que podem conter credenciais.
        logger.warning("Limpeza de avatar pendente após atualização do perfil")
        return False


def save_profile(form, profile_id):
    storage = MemberProfile._meta.get_field("avatar").storage
    uploaded = None
    try:
        # Exige commit próprio: rollback externo não pode abandonar um upload.
        with transaction.atomic(durable=True):
            profile = MemberProfile.objects.select_for_update().get(pk=profile_id)
            old_name = profile.avatar.name
            form.save()
            if form.cleaned_data.get("remover_avatar"):
                profile.avatar = ""
            elif form.cleaned_data.get("avatar"):
                avatar = form.cleaned_data["avatar"]
                name = f"{uuid4().hex}{PurePosixPath(avatar.name).suffix}"
                profile.avatar.save(name, avatar, save=False)
                uploaded = profile.avatar.name
            profile.save()
            if old_name and old_name != profile.avatar.name:
                transaction.on_commit(lambda: remove_unused_avatar(storage, old_name), robust=True)
            return profile
    except Exception:
        if uploaded:
            remove_unused_avatar(storage, uploaded)
        raise
