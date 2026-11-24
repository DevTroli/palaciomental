"""Identidade de conta compartilhada pelos fluxos de cadastro e perfil."""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.functions import Lower, Trim

from .models import MemberProfile

EMAIL_INDEX = "pm_user_email_normalized_unique"
EMAIL_ERROR = "Este e-mail já está cadastrado. Entre com sua conta ou use outro endereço."


def email_users(email):
    return get_user_model().objects.annotate(normalized_email=Lower(Trim("email"))).filter(
        normalized_email=email.strip().lower())


def is_email_conflict(error):
    cause = error.__cause__
    constraint = getattr(getattr(cause, "diag", None), "constraint_name", None)
    return constraint == EMAIL_INDEX or EMAIL_INDEX in str(cause)


def register_account(form):
    try:
        with transaction.atomic():
            user = form.save()
            MemberProfile.objects.create(user=user)
            return user
    except IntegrityError as exc:
        if not is_email_conflict(exc):
            raise
        form.add_error("email", EMAIL_ERROR)
        return None
