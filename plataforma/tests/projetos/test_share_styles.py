"""Contratos estaticos do compartilhamento institucional; sem banco."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]


class ProjectShareStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = (ROOT / "static/css/project-share.css").read_text(encoding="utf-8")

    def test_hidden_panel_has_explicit_scoped_guard(self):
        self.assertRegex(self.css, r"\.tenant-shell \.project-share-panel\[hidden\]\s*\{\s*display:\s*none;")

    def test_open_panel_keeps_horizontal_auto_margins(self):
        self.assertRegex(self.css, r"\.tenant-shell \.share-panel\.project-share-panel:not\(\[hidden\]\)\s*\{\s*margin:\s*0 auto 20px;")

    def test_mobile_copy_row_has_automatic_basis(self):
        self.assertRegex(self.css, r"@media\s*\(max-width:\s*600px\)\s*\{\s*\.tenant-shell \.project-share-panel \.share-copy\s*\{\s*flex:\s*0 1 auto;")

    def test_shared_template_loads_the_fix(self):
        source = (ROOT / "templates/institutional/partials/theme.html").read_text(encoding="utf-8")
        self.assertIn("css/project-share.css", source)


if __name__ == "__main__":
    unittest.main()
