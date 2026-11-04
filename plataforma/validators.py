from pathlib import Path
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image


MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_LOGO_DIMENSION = 2000
MIN_LOGO_DIMENSION = 64
MAX_LOGO_ASPECT_RATIO = 8
NORMALIZED_LOGO_MAX_DIMENSION = 1600
NORMALIZED_LOGO_QUALITY = 86

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


def normalizar_logo(arquivo, nome):
    """Reduz dimensões e remove metadados desnecessários antes do storage."""
    arquivo.seek(0)
    imagem = Image.open(arquivo)
    imagem.thumbnail((NORMALIZED_LOGO_MAX_DIMENSION, NORMALIZED_LOGO_MAX_DIMENSION), Image.Resampling.LANCZOS)
    extensao = Path(nome).suffix.lower()
    formato = "PNG" if extensao == ".png" else "WEBP" if extensao == ".webp" else "JPEG"
    if formato == "JPEG":
        if imagem.mode in {"RGBA", "LA"}:
            fundo = Image.new("RGB", imagem.size, "white")
            fundo.paste(imagem, mask=imagem.getchannel("A"))
            imagem = fundo
        else:
            imagem = imagem.convert("RGB")
    elif formato == "PNG" and imagem.mode not in {"RGB", "RGBA"}:
        imagem = imagem.convert("RGBA")
    buffer = BytesIO()
    opcoes = {"optimize": True}
    if formato in {"JPEG", "WEBP"}:
        opcoes["quality"] = NORMALIZED_LOGO_QUALITY
    imagem.save(buffer, format=formato, **opcoes)
    buffer.seek(0)
    return ContentFile(buffer.read(), name=Path(nome).name)


def caminho_logo(instance, filename):
    organizacao_id = instance.organizacao_id or "pendente"
    return f"tenants/{organizacao_id}/branding/logo/{instance.id}{Path(filename).suffix.lower()}"
