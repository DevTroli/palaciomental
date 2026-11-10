"""Gera imagens sintéticas, sem dados de instituição ou usuário real."""
from pathlib import Path

from PIL import Image, ImageDraw

target = Path("docs/testing/postman/fixtures")
target.mkdir(parents=True, exist_ok=True)
logo = Image.new("RGB", (128, 128), "#6E4AA3")
draw = ImageDraw.Draw(logo)
draw.rectangle((24, 24, 104, 104), outline="white", width=8)
logo.save(target / "logo.png")
cover = Image.new("RGB", (1200, 400), "#315A76")
draw = ImageDraw.Draw(cover)
draw.rectangle((800, 0, 1200, 400), fill="#6E4AA3")
draw.ellipse((480, -100, 900, 320), fill="#5C9F63")
cover.save(target / "cover.png")
