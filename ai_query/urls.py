from django.urls import path
from .views import ai_query, export_excel

urlpatterns = [
    path("ai-query/", ai_query, name="ai_query"),
    path("export-excel/", export_excel, name="export_excel"),
]