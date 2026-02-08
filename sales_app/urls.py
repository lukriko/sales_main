from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Dashboard
    path('', views.dashboard, name='sales_dashboard'),

    path('another/', views.plan_workflow, name='another'),
    path('employees/', views.employee_analytics, name='employee_analytics'),
    path('query/', views.query, name='query'),
    path('export/csv/', views.export_location_csv, name='export_location_csv'),
    path('insights/', views.insights, name='insights'),
]