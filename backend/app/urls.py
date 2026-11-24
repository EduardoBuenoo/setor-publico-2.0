from django.contrib import admin
from django.urls import path, include
from .health import health

urlpatterns = [
    path('health/', health, name='health'),
    path('admin/', admin.site.urls),
    
    # Rotas da API baseadas no padrão example (prefixadas com api/v1/)
    path('api/v1/', include('users.urls')),
    path('api/v1/', include('sector.urls')),
    path('api/v1/', include('ai_docs.urls')),
]
