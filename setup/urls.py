from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from listaEspera.sitemaps import StaticViewSitemap, WaitlistSitemap

sitemaps = {
    "static": StaticViewSitemap,
    "waitlist": WaitlistSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("listaEspera.urls")),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
]
