from django.conf import settings
from django.http import JsonResponse


def health_view(request):
    return JsonResponse(
        {
            "status": "ok",
            "version": settings.VERSION,
            "env": getattr(settings, "ENV", "dev"),
        }
    )
