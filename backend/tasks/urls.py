"""
URL configuration for the tasks app.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.api_info, name='api-info'),
    path('tasks/analyze/', views.analyze_tasks, name='analyze-tasks'),
    path('tasks/suggest/', views.suggest_tasks, name='suggest-tasks'),
    path('tasks/strategies/', views.get_strategies, name='get-strategies'),
    # New utility endpoints
    path('tasks/detect-patterns/', views.detect_patterns, name='detect-patterns'),
    path('tasks/time-context/', views.get_time_context, name='time-context'),
    path('tasks/fatigue/', views.calculate_fatigue, name='calculate-fatigue'),
    # Export endpoints
    path('tasks/export/json/', views.export_json, name='export-json'),
    path('tasks/export/csv/', views.export_csv, name='export-csv'),
]
