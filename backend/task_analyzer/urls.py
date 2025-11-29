"""
URL configuration for task_analyzer project.
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def home_view(request):
    """Root endpoint with API information."""
    return JsonResponse({
        'message': 'Welcome to Smart Task Analyzer API',
        'version': '2.0.0',
        'endpoints': {
            'API Root': '/api/',
            'Analyze Tasks': 'POST /api/tasks/analyze/',
            'Suggest Tasks': 'POST /api/tasks/suggest/',
            'Strategies': 'GET /api/tasks/strategies/',
            'API Documentation': '/api/docs/',
            'OpenAPI Schema': '/api/schema/',
        },
        'frontend': 'Open frontend/index.html in your browser'
    })


urlpatterns = [
    path('', home_view, name='home'),
    path('admin/', admin.site.urls),
    path('api/', include('tasks.urls')),
    # OpenAPI/Swagger Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
