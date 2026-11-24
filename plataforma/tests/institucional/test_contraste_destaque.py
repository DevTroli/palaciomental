"""Contraste numerico e contratos de tokens; nao substitui validacao visual."""
from pathlib import Path
import unittest

from plataforma.theme import accent_text_tokens, contrast

ROOT = Path(__file__).resolve().parents[3]
COLORS = ("#000000", "#FFFFFF", "#FFFF00", "#777777", "#808080", "#FF0000", "#0000FF", "#00FFFF")


class AccentContrastTests(unittest.TestCase):


    def test_extreme_palette_matrix(self):
        for accent in COLORS:
            for index, background in enumerate(COLORS):
                surface = COLORS[-index - 1]
                tokens = accent_text_tokens(accent, background, surface)
                contexts = (("tenant_accent_foreground_color", background),
                            ("tenant_surface_accent_foreground_color", surface),
                            ("tenant_dark_accent_foreground_color", "#101820"),
                            ("tenant_dark_surface_accent_foreground_color", "#1B2836"))
                for key, backdrop in contexts:
                    with self.subTest(accent=accent, background=backdrop, token=key):
                        self.assertGreaterEqual(contrast(tokens[key], backdrop), 4.5)


if __name__ == "__main__":
    unittest.main()
