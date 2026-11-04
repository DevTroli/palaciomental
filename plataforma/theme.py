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
