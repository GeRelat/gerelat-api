from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from .views import health_view

urlpatterns = [
    path("", include("apps.gerelat.urls")),
    path("admin/", admin.site.urls),
    path("auth/", include("apps.accounts.urls")),
    path("health/", health_view, name="health"),
]

if settings.DEBUG:

    def trigger_error(request):
        raise ZeroDivisionError("Sentry debug trigger")

    urlpatterns += [
        path("schema/", SpectacularAPIView.as_view(), name="schema"),
        path("docs/", SpectacularSwaggerView.as_view(url_name="schema")),
        path("silk/", include("silk.urls", namespace="silk")),
        path("sentry-debug/", trigger_error),
    ]
