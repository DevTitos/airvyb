from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from notifications.views import subscribe

urlpatterns = [
    path('auth/admin/', admin.site.urls),
    path('', views.HomeView.as_view(), name='home'),
    path('', include('account.urls')),
    path('', include('core.urls')),
    path('', include('finance.urls')),
    path('activation/', include('activation.urls')),
    path('deals/', include('deals.urls')),
    path("webpush/", include("webpush.urls")),
    path('notifications/subscribe/', subscribe, name='subscribe'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)