from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap para páginas estáticas do site."""
    priority = 1.0
    changefreq = "weekly"

    def items(self):
        return ["core:index", "listaEspera:projects", "listaEspera:status", "listaEspera:saude"]

    def location(self, item):
        return reverse(item)


class WaitlistSitemap(Sitemap):
    """Sitemap para a página de lista de espera (mesma que index)."""
    priority = 1.0
    changefreq = "daily"

    def items(self):
        return ["core:index"]

    def location(self, item):
        return reverse(item)
