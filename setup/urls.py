from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.generic import RedirectView

from camp import views as camp_views
from plataforma.sitemaps import StaticViewSitemap

sitemaps = {"static": StaticViewSitemap}
handler403 = "plataforma.error_views.permission_denied"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("favicon.ico", RedirectView.as_view(url=f"{settings.STATIC_URL}favicon.ico", permanent=False), name="favicon"),
    # Acesso de demonstração ao CAMP (apenas com DEBUG=True).
    # Fica sob /entrar/ para ser liberado pelo middleware de tenant.
    path("entrar/camp/", camp_views.demo_login, name="camp_demo_login"),
    path("", include("core.urls")),
    path("", include("plataforma.urls")),
    path("camp/", include("camp.urls")),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
