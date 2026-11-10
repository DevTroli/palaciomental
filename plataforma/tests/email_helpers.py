from django.core.mail import EmailMessage, EmailMultiAlternatives


def html_alternative(message: EmailMessage) -> str:
    """Require the text HTML alternative expected from invitation senders."""
    assert isinstance(message, EmailMultiAlternatives)
    content, mimetype = message.alternatives[0]
    assert mimetype == "text/html"
    assert isinstance(content, str)
    return content
