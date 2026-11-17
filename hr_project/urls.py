from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from shop import views

urlpatterns = [
    path('', views.index, name='index'),
    path('admin/', admin.site.urls),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/notifications/', views.notifications_page, name='notifications_page'),
    path('api/orders/', views.api_orders, name='api_orders'),
    path('api/orders/live-status/', views.api_order_status_public, name='api_order_status_public'),
    path('api/orders/<str:code>/status/', views.api_order_status, name='api_order_status'),
    path('api/export/csv/', views.export_csv, name='export_csv'),
    path('api/export/json/', views.export_json, name='export_json'),
    path('<str:filename>', views.static_page, name='static_page'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
