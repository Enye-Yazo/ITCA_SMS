# itca_portal/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # Django admin — emergency access only
    path('admin/', admin.site.urls),

    # Microsoft Entra ID authentication via OIDC
    path('oidc/', include('mozilla_django_oidc.urls')),

    # Dashboard — root of the portal
    path('dashboard/', include('dashboard.urls')),

    path('admissions/', include('admissions.urls')),

    path('academics/', include('academics.urls')),

    # Redirect root to dashboard
    path('', include('dashboard.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
