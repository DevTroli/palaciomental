"""Identidade visual compartilhada por telas e mensagens institucionais."""

from django.templatetags.static import static

from .navigation import global_home_url
from .validators import CORES_SEMANTICAS


def contrasting_text(color):
    """Escolhe preto ou branco pelo maior contraste WCAG com uma cor sRGB."""
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    luminance = sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    return "#000000" if luminance > 0.179 else "#ffffff"


def organization_branding(organization):
    identity = getattr(organization, "identidade", None)
    primary = CORES_SEMANTICAS.get(
        getattr(identity, "cor_primaria", ""), CORES_SEMANTICAS["roxo-institucional"]
    )
    accent = CORES_SEMANTICAS.get(
        getattr(identity, "cor_destaque", ""), CORES_SEMANTICAS["verde-institucional"]
    )
    return {
        "tenant_display_name": getattr(identity, "nome_exibicao", "") or organization.nome,
        "tenant_identidade": identity,
        "tenant_logo_url": identity.logo.url if identity and identity.logo else "",
        "tenant_primary_color": primary,
        "tenant_accent_color": accent,
        "tenant_primary_text_color": contrasting_text(primary),
        "tenant_accent_text_color": contrasting_text(accent),
        "tenant_background_color": CORES_SEMANTICAS.get(
            getattr(identity, "cor_fundo", ""), CORES_SEMANTICAS["bege-claro"]
        ),
    }


def invitation_branding(request, organization):
    """E-mails não têm context processors e precisam de URLs absolutas."""
    context = organization_branding(organization)
    if context["tenant_logo_url"]:
        context["tenant_logo_url"] = request.build_absolute_uri(context["tenant_logo_url"])
    context["pm_home_url"] = global_home_url(request)
    context["pm_logo_url"] = request.build_absolute_uri(static("img/mind_palace_logo.png"))
    return context
