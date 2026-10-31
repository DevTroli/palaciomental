from django.test import TestCase
from django.urls import reverse


class CoreEntryPointTests(TestCase):
    def test_root_is_the_product_home(self):
        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")
        self.assertContains(response, "Dê continuidade às suas ideias.")

    def test_removed_legacy_feature_is_not_in_the_root_sitemap(self):
        response = self.client.get(reverse("django.contrib.sitemaps.views.sitemap"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/")
        self.assertNotContains(response, "/lista-espera/")
