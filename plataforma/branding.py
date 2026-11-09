"""Identidade visual compartilhada por telas e mensagens institucionais."""

from django.templatetags.static import static

from .navigation import global_home_url
from .validators import CORES_SEMANTICAS
from .theme import COLOR_ROLES, HEX_COLOR, brand_background, contrast, readable_color, text_on


def contrasting_text(color):
    """Escolhe preto ou branco pelo maior contraste WCAG com uma cor sRGB."""
    return text_on(color)


def organization_branding(organization):
    identity = getattr(organization, "identidade", None)
    primary = CORES_SEMANTICAS.get(
        getattr(identity, "cor_primaria", ""), CORES_SEMANTICAS["roxo-institucional"]
    )
    accent = CORES_SEMANTICAS.get(
        getattr(identity, "cor_destaque", ""), CORES_SEMANTICAS["verde-institucional"]
    )
    background = CORES_SEMANTICAS.get(
        getattr(identity, "cor_fundo", ""), CORES_SEMANTICAS["bege-claro"]
    )
    colors = dict(primary=primary, secondary=primary, accent=accent, background=background, surface="#ffffff")
    custom = getattr(identity, "tema", {})
    if isinstance(custom, dict):
        for role in COLOR_ROLES:
            value = custom.get(role)
            if isinstance(value, str) and HEX_COLOR.fullmatch(value):
                colors[role] = value.upper()
    primary, accent = colors["primary"], colors["accent"]
    solid = brand_background(primary)
    footer = solid if contrast(solid, colors["background"]) >= 3 else text_on(colors["background"])
    selection = solid if contrast(solid, colors["surface"]) >= 3 else text_on(colors["surface"])
    return {
        "tenant_solid_color": solid,
        "tenant_selection_color": selection,
        "tenant_selection_text_color": text_on(selection),
        "tenant_footer_color": footer,
        "tenant_footer_text_color": text_on(footer),
        "tenant_display_name": getattr(identity, "nome_exibicao", "") or organization.nome,
        "tenant_identidade": identity,
        "tenant_logo_url": identity.logo.url if identity and identity.logo else "",
        "tenant_cover_url": identity.capa.url if identity and getattr(identity, "capa", None) else "",
        "tenant_presentation": getattr(identity, "apresentacao", ""),
        "tenant_primary_color": primary,
        "tenant_accent_color": accent,
        "tenant_primary_text_color": contrasting_text(primary),
        "tenant_accent_text_color": contrasting_text(accent),
        "tenant_background_color": colors["background"],
        "tenant_secondary_color": colors["secondary"],
        "tenant_secondary_text_color": text_on(colors["secondary"]),
        "tenant_surface_color": colors["surface"],
        "tenant_background_text_color": text_on(colors["background"]),
        "tenant_surface_text_color": text_on(colors["surface"]),
        "tenant_link_color": readable_color(primary, colors["background"]),
        "tenant_surface_link_color": readable_color(primary, colors["surface"]),
        "tenant_colors": colors,
    }


def invitation_branding(request, organization):
    """E-mails não têm context processors e precisam de URLs absolutas."""
    context = organization_branding(organization)
    if context["tenant_logo_url"]:
        context["tenant_logo_url"] = request.build_absolute_uri(context["tenant_logo_url"])
    if context["tenant_cover_url"]:
        context["tenant_cover_url"] = request.build_absolute_uri(context["tenant_cover_url"])
    context["pm_home_url"] = global_home_url(request)
    context["pm_logo_url"] = request.build_absolute_uri(static("img/mind_palace_logo.png"))
    return context
