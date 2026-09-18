from django.contrib import admin
from django.urls import path, include
from apps.node_compat.views import HealthView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HealthView.as_view()),
    path('api/health', HealthView.as_view()),
    path('api/', include('apps.node_compat.urls')),
]
