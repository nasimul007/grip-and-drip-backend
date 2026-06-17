from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from apps.seo.sitemaps import sitemaps

urlpatterns = [
    path("admin/", admin.site.urls),
    # API
    path("api/categories/", include("apps.categories.urls")),
    path("api/products/", include("apps.products.urls")),
    path("api/search/", include("apps.products.search_urls")),
    path("api/seo/", include("apps.seo.urls")),
    # Sitemap
    path("api/sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap-xml"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
