"""Backend transacional Resend via HTTPS, sem dependência de SMTP."""

import json
import uuid
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class EmailDeliveryError(RuntimeError):
    """Erro sanitizado: nunca inclui chave, corpo ou token do convite."""


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or ():
            if not message.recipients():
                continue
            try:
                self._send_message(message)
            except (EmailDeliveryError, ImproperlyConfigured):
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent

    @staticmethod
    def _send_message(message):
        key = settings.RESEND_API_KEY
        if not key:
            raise ImproperlyConfigured("Configure RESEND_API_KEY para enviar e-mails.")
        if message.attachments:
            raise EmailDeliveryError("Este backend ainda não suporta anexos.")
        message.message()  # Validação de cabeçalhos do próprio Django.
        payload = {
            "from": message.from_email,
            "to": message.to,
            "subject": message.subject,
            "html" if message.content_subtype == "html" else "text": message.body,
        }
        for content, mimetype in getattr(message, "alternatives", ()):
            if mimetype == "text/html":
                payload["html"] = content
        for field in ("cc", "bcc", "reply_to"):
            if getattr(message, field):
                payload[field] = getattr(message, field)
        request = Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "PalacioMental/transactional-email",
                "Idempotency-Key": message.extra_headers.get("Idempotency-Key", str(uuid.uuid4())),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=settings.RESEND_TIMEOUT) as response:  # nosec B310: URL HTTPS fixa da Resend, sem entrada externa
                result = json.load(response)
                message_id = result.get("id") if isinstance(result, dict) else None
                if not isinstance(message_id, str) or not message_id.strip():
                    raise EmailDeliveryError("O provedor não confirmou o envio do e-mail.")
        except (OSError, ValueError):
            raise EmailDeliveryError("Falha na comunicação com o provedor de e-mail.") from None
