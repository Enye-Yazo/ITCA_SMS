# itca_portal/urls.py

from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


def health_check(request):
    """
    Liveness/readiness probe target for Azure Container Apps. Deliberately
    has no auth and does no DB query — a probe hitting this every few
    seconds shouldn't cost a database round trip or ever get bounced into
    the OIDC login flow.
    """
    return HttpResponse("ok")


urlpatterns = [
    path('healthz/', health_check, name='health_check'),

    # Django admin — emergency access only
    path('admin/', admin.site.urls),

    # Microsoft Entra ID authentication via OIDC
    path('oidc/', include('mozilla_django_oidc.urls')),

    # Dashboard — root of the portal
    path('dashboard/', include('dashboard.urls')),

    path('admissions/', include('admissions.urls')),

    path('academics/', include('academics.urls')),

    path('assessments/', include('assessments.urls')),

    # Public landing page at root; also the post-login redirect target
    path('', include('accounts.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
