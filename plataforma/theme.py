"""Tokens de marca, sem CSS livre e com compatibilidade com as paletas antigas."""

import re

from django.core.exceptions import ValidationError

COLOR_ROLES = ("primary", "secondary", "accent", "background", "surface")
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_theme(value):
    if not isinstance(value, dict) or set(value) - set(COLOR_ROLES):
        raise ValidationError("A identidade aceita somente os cinco papéis de cor definidos.")
    if any(not isinstance(color, str) or not HEX_COLOR.fullmatch(color) for color in value.values()):
        raise ValidationError("Use cores no formato hexadecimal #RRGGBB, sem transparência.")


def luminance(color):
    values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))


def contrast(first, second):
    a, b = sorted((luminance(first), luminance(second)))
    return (b + .05) / (a + .05)


def text_on(color):
    return "#000000" if luminance(color) > .179 else "#ffffff"


def readable_color(color, background):
    return color if contrast(color, background) >= 4.5 else text_on(background)


def brand_background(color):
    """Escurece a cor de marca apenas o suficiente para texto branco legível."""
    channels = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    for factor in range(255, -1, -1):
        candidate = "#" + "".join(f"{channel * factor // 255:02X}" for channel in channels)
        if contrast(candidate, "#FFFFFF") >= 4.7:
            return candidate


def accent_text_tokens(accent, background, surface):
    """Deriva texto de destaque sem alterar a marca; fundos dark seguem tenant-shell.css."""
    return {
        "tenant_accent_foreground_color": readable_color(accent, background),
        "tenant_surface_accent_foreground_color": readable_color(accent, surface),
        "tenant_dark_accent_foreground_color": readable_color(accent, "#101820"),
        "tenant_dark_surface_accent_foreground_color": readable_color(accent, "#1B2836"),
    }
