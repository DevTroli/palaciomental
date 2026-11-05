from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap para páginas estáticas do site."""
    priority = 1.0
    changefreq = "weekly"

    def items(self):
        return ["core:index", "plataforma:projects", "plataforma:status", "plataforma:saude"]

    def location(self, item):
        return reverse(item)
