"""Feedback honesto de envio; o convite continua revogável em caso de falha."""

import logging

from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured

from .email_backends import EmailDeliveryError


logger = logging.getLogger(__name__)


def deliver_invitation(request, sender, invitation, token):
    try:
        sender(request, invitation, token)
    except (EmailDeliveryError, ImproperlyConfigured, OSError) as exc:
        logger.warning("Falha no envio do convite %s (%s).", invitation.pk, type(exc).__name__)
        messages.error(
            request,
            "Convite registrado, mas o envio do e-mail falhou. "
            "Após corrigir o envio, revogue este convite e emita outro.",
        )
    else:
        messages.success(request, f"Convite encaminhado para envio a {invitation.email}.")
