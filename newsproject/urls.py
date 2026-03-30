"""
Root URL configuration for newsproject.
Includes routes for the news app, REST API, and JWT authentication.
"""

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # News application (web UI)
    path('', include('news.urls')),

    # JWT token endpoints
    path(
        'api/token/',
        TokenObtainPairView.as_view(),
        name='token_obtain_pair',
    ),
    path(
        'api/token/refresh/',
        TokenRefreshView.as_view(),
        name='token_refresh',
    ),

    # REST API endpoints
    path('api/', include('news.api_urls')),
]
