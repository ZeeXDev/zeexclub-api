# backend/urls.py
"""
URLs principales du projet ZeeXClub
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

# Page d'accueil API
def api_home(request):
    return JsonResponse({
        "status": "✅ ZeeXClub API is running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/health/",
            "recent": "/api/videos/recent/",
            "search": "/api/videos/search/",
            "folders": "/api/folders/",
            "stream": "/api/stream/<id>/",
        },
        "documentation": "https://github.com/ton-repo/zeexclub"
    })

urlpatterns = [
    path('', api_home),  # ← Page d'accueil sur /
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]

# Servir les fichiers médias en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
