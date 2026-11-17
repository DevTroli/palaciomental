from django.test import TestCase
from django.urls import reverse


class HomepageTests(TestCase):
    def test_root_returns_product_home(self):
        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")
        self.assertContains(response, "Dê continuidade às suas ideias.")

    def test_public_monitoring_markers_identify_the_expected_pages(self):
        for route, marker in (
            ("core:index", "inicio"),
            ("plataforma:projects", "vitrine"),
            ("plataforma:login", "entrada"),
            ("plataforma:register", "cadastro"),
        ):
            with self.subTest(route=route):
                self.assertContains(self.client.get(reverse(route)), f'data-status-probe="{marker}"')


class StatusViewTests(TestCase):
    def test_pagina_tecnica_antiga_nao_esta_publica(self):
        self.assertEqual(self.client.get("/status").status_code, 404)
        self.assertEqual(self.client.get("/status/").status_code, 404)
        self.assertEqual(self.client.get("/saude").json(), {"status": "ok"})
