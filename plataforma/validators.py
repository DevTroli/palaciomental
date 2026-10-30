from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image


MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_LOGO_DIMENSION = 2000
MIN_LOGO_DIMENSION = 64
MAX_LOGO_ASPECT_RATIO = 8

# Chaves semânticas: a interface mostra nome e amostra; o backend só aceita valores controlados.
CORES_SEMANTICAS = {
    "roxo-institucional": "#6E4AA3",
    "verde-institucional": "#5C9F63",
    "bege-claro": "#F3ECDF",
    "azul-sobrio": "#315A76",
    "terracota": "#A75D45",
    "neutro-claro": "#F5F5F2",
}

ROTULOS_CORES = {
    "roxo-institucional": "Roxo institucional",
    "verde-institucional": "Verde institucional",
    "bege-claro": "Bege claro",
    "azul-sobrio": "Azul sóbrio",
    "terracota": "Terracota",
    "neutro-claro": "Neutro claro",
}


def validar_logo(arquivo):
    if not arquivo:
        return
    if arquivo.size > MAX_LOGO_BYTES:
        raise ValidationError("A logo deve ter no máximo 2 MB.")
    extensao = Path(arquivo.name).suffix.lower()
    if extensao not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValidationError("Envie a logo em PNG, JPEG ou WebP.")
    try:
        imagem = Image.open(arquivo)
        imagem.verify()
        arquivo.seek(0)
        imagem = Image.open(arquivo)
        largura, altura = imagem.size
    except Exception as exc:
        raise ValidationError("O arquivo enviado não é uma imagem válida.") from exc
    if min(largura, altura) < MIN_LOGO_DIMENSION:
        raise ValidationError("A logo deve ter pelo menos 64 pixels no menor lado.")
    if max(largura, altura) > MAX_LOGO_DIMENSION:
        raise ValidationError("A logo deve ter no máximo 2.000 pixels no maior lado.")
    if max(largura / altura, altura / largura) > MAX_LOGO_ASPECT_RATIO:
        raise ValidationError("A proporção da logo não pode ultrapassar 8:1.")
    arquivo.seek(0)


def caminho_logo(instance, filename):
    organizacao_id = instance.organizacao_id or "pendente"
    return f"tenants/{organizacao_id}/branding/logo/{instance.id}{Path(filename).suffix.lower()}"
