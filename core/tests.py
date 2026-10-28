from django.test import TestCase
from django.urls import reverse


class CoreEntryPointTests(TestCase):
    def test_root_is_the_mvp_home(self):
        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")
        self.assertContains(response, "Dê continuidade às suas ideias.")

    def test_legacy_mvp_path_redirects_to_root(self):
        response = self.client.get(reverse("core:mvp_legacy"))

        self.assertRedirects(response, reverse("core:index"), status_code=301)

    def test_waitlist_is_not_in_the_root_sitemap(self):
        response = self.client.get(reverse("django.contrib.sitemaps.views.sitemap"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/")
        self.assertNotContains(response, "/lista-espera/")
